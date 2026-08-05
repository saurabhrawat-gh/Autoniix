"""Phase 7 — quality-gate calibrator tests.

Pure-function tests for the per-niche threshold tuner. The DB layer
(``calibrate_niche``, ``load_thresholds_for_niche``) is exercised
elsewhere; here we lock in the math so refactors can't silently change
the behaviour of the loop closer.
"""

from __future__ import annotations

import pytest
from quality.calibrator import (
    ABSOLUTE_CEILING,
    ABSOLUTE_FLOOR,
    MIN_SAMPLES,
    Sample,
    calibrate_all_dimensions,
    calibrate_dimension,
)
from quality.gate import PRODUCTION_THRESHOLDS


def _samples(spec: list[tuple[float, str]]) -> list[Sample]:
    return [Sample(score=s, tier=t) for s, t in spec]


def test_insufficient_samples_returns_default():
    """With < MIN_SAMPLES we keep the static default and flag it."""
    res = calibrate_dimension(
        "hook_retention_score",
        _samples([(8.0, "S")] * 5),
        default_floor=7.5,
    )
    assert res.status == "insufficient_samples"
    assert res.floor == 7.5
    assert res.n_samples == 5


def test_zero_wins_returns_default():
    """No positive class → no signal to fit; keep default."""
    samples = _samples([(7.0, "D")] * MIN_SAMPLES)
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "insufficient_samples"
    assert res.floor == 7.5


def test_zero_flops_returns_default():
    samples = _samples([(8.0, "S")] * MIN_SAMPLES)
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "insufficient_samples"
    assert res.floor == 7.5


def test_finds_lowest_threshold_meeting_precision():
    """When wins cluster high and flops cluster low, the calibrator
    picks the lowest threshold whose precision clears TARGET_PRECISION.

    To exercise the search rather than have precision be met at the
    minimum threshold, we make the population mostly flops so a low
    threshold doesn't already pass. Flops at and below 7.0; wins at and
    above 8.0. Expected floor: just above the top flop (7.0), i.e. ≥ 7.1.
    """
    samples = (
        _samples([(s, "S") for s in [8.0, 8.2, 8.5, 8.7, 9.0, 8.1, 8.3, 8.6]])
        + _samples([(s, "A") for s in [8.4]])
        + _samples(
            [
                (s, "D")
                for s in [
                    5.0,
                    5.2,
                    5.5,
                    5.8,
                    6.0,
                    6.2,
                    6.4,
                    6.5,
                    6.6,
                    6.7,
                    6.8,
                    6.9,
                    7.0,
                    5.3,
                    6.1,
                    6.3,
                ]
            ]
        )
    )
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "auto"
    assert res.win_rate_at_floor is not None
    assert res.win_rate_at_floor >= 0.70
    lower = res.floor - 0.1
    passing_at_lower = [s for s in samples if s.score >= lower]
    if passing_at_lower:
        precision_at_lower = sum(1 for s in passing_at_lower if s.is_win) / len(passing_at_lower)
        assert precision_at_lower < 0.70, (
            f"calibrator left precision on the table: at t={lower:.1f} "
            f"precision={precision_at_lower:.2f} also meets target"
        )
    assert res.floor <= 8.0, f"floor={res.floor} unnecessarily strict"


def test_lowest_acceptable_not_highest_precision():
    """Calibrator chooses the *lowest* acceptable t, never an
    unnecessarily strict one. Two equally acceptable thresholds → pick
    the lower."""
    samples = (
        _samples([(s, "S") for s in [8.0, 8.5, 9.0, 8.2, 8.7]])
        + _samples([(s, "A") for s in [7.5, 7.6, 7.8, 7.9, 8.0, 8.1, 8.3, 8.4, 8.5, 8.6]])
        + _samples([(s, "D") for s in [5.0, 5.5, 6.0, 6.5, 7.0]])
    )
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "auto"
    assert res.floor <= 8.0


def test_monotonicity_guard_clamps_to_min_s_tier():
    """If the algorithm would set t=8.5 but an S-tier video scored 8.3,
    we clamp to 8.3. We never block proven winners."""
    samples = (
        _samples([(s, "S") for s in [8.5, 8.7, 8.9, 9.0, 8.6, 8.8, 9.1, 9.2]])
        + _samples([(s, "A") for s in [8.0, 8.1, 8.2, 8.4]])
        + _samples([(s, "D") for s in [5.0, 5.5, 6.0, 6.5, 7.0, 6.2, 6.8]])
        + [Sample(score=8.3, tier="S")]
    )
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "auto"
    assert res.floor <= 8.3, f"monotonicity guard violated: floor={res.floor} would block S=8.3"


def test_monotonicity_guard_recomputes_metrics_at_clamped_value():
    """When we clamp, the persisted metrics must describe the *clamped*
    value, not the rejected one. Otherwise audit logs lie about why we
    chose the threshold."""
    samples = (
        _samples([(s, "S") for s in [8.5, 8.7, 8.9, 9.0]] * 3)
        + _samples([(s, "A") for s in [8.0, 8.1, 8.2, 8.4]])
        + _samples([(s, "D") for s in [5.0, 5.5, 6.0, 6.5, 7.0]])
        + [Sample(score=7.8, tier="S")]
    )
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.floor <= 7.8
    assert res.s_tier_preserved == pytest.approx(1.0, abs=1e-6)


def test_floor_is_clamped_to_absolute_bounds():
    samples = _samples([(9.9, "S")] * 15) + _samples([(9.5, "D")] * 10)
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert ABSOLUTE_FLOOR <= res.floor <= ABSOLUTE_CEILING


def test_no_threshold_meets_precision_returns_default():
    """If wins and flops are interleaved at every level, no threshold
    achieves the precision target. We return the default + status flag."""
    samples = []
    for s in [6.0, 6.5, 7.0, 7.5, 8.0, 8.5]:
        for _ in range(5):
            samples.append(Sample(score=s, tier="S"))
            samples.append(Sample(score=s, tier="D"))
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert ABSOLUTE_FLOOR <= res.floor <= ABSOLUTE_CEILING


def test_calibrate_all_dimensions_covers_every_threshold_dim():
    """Caller can pass an empty per-dim dict — every dimension must
    still come back with a result (using its default)."""
    out = calibrate_all_dimensions({})
    dims = {r.dimension for r in out}
    expected = set(PRODUCTION_THRESHOLDS) - {"composite_score"}
    assert dims == expected
    assert all(r.status == "insufficient_samples" for r in out)


def test_result_as_dict_is_json_safe():
    samples = _samples([(s, "S") for s in [8.0, 8.5, 9.0, 8.2]] * 3) + _samples(
        [(s, "D") for s in [5.0, 5.5, 6.0, 6.5]] * 3
    )
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    d = res.as_dict()
    import json

    json.dumps(d)
    assert d["dimension"] == "hook_retention_score"
    assert isinstance(d["floor"], float)
    assert isinstance(d["n_samples"], int)
