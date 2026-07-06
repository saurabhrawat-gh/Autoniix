"""Phase 9 — augmented calibrator: per-dim retention labels.

These tests lock the augmentation: when a sample carries a measured
retention label, the calibrator uses it instead of tier; otherwise
behaviour is identical to Phase 7. The pre-existing 11 P7 tests in
``test_gate_calibrator.py`` continue to validate the unchanged paths.
"""
from __future__ import annotations

import pytest

from quality.calibrator import (
    DIM_TO_RETENTION_FEATURE,
    RETENTION_LOWER_IS_BETTER,
    Sample,
    _classify_by_retention,
    _niche_median,
    _samples_by_dimension,
    calibrate_dimension,
)




def test_sample_default_uses_tier_for_classification():
    """Phase 7 behaviour preserved: no retention_label → tier rules."""
    assert Sample(score=8.0, tier="S").is_win is True
    assert Sample(score=8.0, tier="A").is_win is True
    assert Sample(score=8.0, tier="B").is_win is False
    assert Sample(score=8.0, tier="D").is_flop is True


def test_sample_retention_label_overrides_tier():
    """When retention_label is set it takes precedence over tier."""
    s = Sample(score=8.0, tier="S", retention_label=False)
    assert s.is_win is False
    assert s.is_flop is True

    s = Sample(score=6.0, tier="D", retention_label=True)
    assert s.is_win is True
    assert s.is_flop is False


def test_sample_retention_label_none_falls_through_to_tier():
    s = Sample(score=8.0, tier="S", retention_label=None)
    assert s.is_win is True
    assert s.is_flop is False




def test_niche_median_returns_none_below_min_count():
    assert _niche_median([0.1, 0.2, 0.3, 0.4]) is None
    assert _niche_median([0.1] * 5) is not None


def test_niche_median_ignores_none_values():
    values = [None, None, 0.1, 0.2, 0.3, 0.4, 0.5]
    assert _niche_median(values) == pytest.approx(0.3)


def test_classify_by_retention_lower_is_better():
    assert _classify_by_retention(0.10, 0.20, lower_is_better=True) is True
    assert _classify_by_retention(0.30, 0.20, lower_is_better=True) is False


def test_classify_by_retention_higher_is_better():
    assert _classify_by_retention(0.80, 0.50, lower_is_better=False) is True
    assert _classify_by_retention(0.30, 0.50, lower_is_better=False) is False


def test_classify_by_retention_at_boundary_returns_none():
    """Samples exactly at the median fall through to tier; this avoids
    arbitrary 50/50 splits that smear the calibration grid."""
    assert _classify_by_retention(0.20, 0.20, lower_is_better=True) is None


def test_classify_by_retention_missing_data_returns_none():
    assert _classify_by_retention(None, 0.20, lower_is_better=True) is None
    assert _classify_by_retention(0.10, None, lower_is_better=True) is None




def test_dim_to_retention_feature_dims_are_real_threshold_dims():
    """Every key in DIM_TO_RETENTION_FEATURE must be an actual gate dim."""
    from quality.gate import PRODUCTION_THRESHOLDS
    for dim in DIM_TO_RETENTION_FEATURE:
        assert dim in PRODUCTION_THRESHOLDS, (
            f"DIM_TO_RETENTION_FEATURE references unknown dim {dim!r}"
        )


def test_dim_to_retention_feature_features_are_lower_is_better():
    """All currently-mapped retention features should be lower-is-better
    (drop / decay metrics). Locking this so a future addition like
    'end_retention' (higher is better) can't slip in without explicit
    update of RETENTION_LOWER_IS_BETTER."""
    for feature in DIM_TO_RETENTION_FEATURE.values():
        assert feature in RETENTION_LOWER_IS_BETTER, (
            f"Feature {feature!r} not registered in RETENTION_LOWER_IS_BETTER"
        )




def _row(*, tier: str, scores: dict, hook_drop: float | None = None,
         mid_decay: float | None = None) -> dict:
    """Build a row shaped like the SQL pull returns."""
    return {
        "performance_tier":  tier,
        "sub_scores":        scores,
        "composite_score":   sum(scores.values()) / max(len(scores), 1),
        "hook_dropoff_30s":  hook_drop,
        "mid_video_decay":   mid_decay,
        "end_retention":     None,
    }


def test_samples_by_dimension_falls_through_to_tier_when_no_curve_data():
    """Zero curves in batch → niche_median returns None → every sample
    in the augmented dim still uses tier."""
    rows = [
        _row(tier="S", scores={"hook_retention_score": 8.5}),
        _row(tier="A", scores={"hook_retention_score": 8.0}),
        _row(tier="D", scores={"hook_retention_score": 5.5}),
    ]
    by_dim, _ = _samples_by_dimension(rows)
    samples = by_dim["hook_retention_score"]
    assert all(s.retention_label is None for s in samples)
    assert samples[0].is_win is True
    assert samples[1].is_win is True
    assert samples[2].is_flop is True


def test_samples_by_dimension_uses_retention_label_when_curves_present():
    """With ≥5 valid hook_drops in the batch, niche_median is computable
    and the relevant samples are labelled by measurement, not tier."""
    rows = [
        _row(tier="S", scores={"hook_retention_score": 8.5}, hook_drop=0.05),
        _row(tier="A", scores={"hook_retention_score": 8.0}, hook_drop=0.10),
        _row(tier="A", scores={"hook_retention_score": 7.8}, hook_drop=0.15),
        _row(tier="B", scores={"hook_retention_score": 7.5}, hook_drop=0.20),
        _row(tier="C", scores={"hook_retention_score": 7.0}, hook_drop=0.25),
        _row(tier="D", scores={"hook_retention_score": 6.0}, hook_drop=0.30),
        _row(tier="D", scores={"hook_retention_score": 5.5}, hook_drop=0.35),
    ]
    by_dim, _ = _samples_by_dimension(rows)
    samples = by_dim["hook_retention_score"]
    assert len(samples) == 7
    assert samples[0].retention_label is True
    assert samples[1].retention_label is True
    assert samples[2].retention_label is True
    assert samples[3].retention_label is None
    assert samples[4].retention_label is False
    assert samples[5].retention_label is False


def test_samples_by_dimension_does_not_apply_retention_label_to_unmapped_dims():
    """Dims not in DIM_TO_RETENTION_FEATURE get retention_label=None
    even if curves are present in the batch."""
    rows = [
        _row(tier="S", scores={"idea_score": 8.5, "thumbnail_score": 8.0}, hook_drop=0.05),
        _row(tier="A", scores={"idea_score": 8.0, "thumbnail_score": 7.8}, hook_drop=0.10),
        _row(tier="A", scores={"idea_score": 7.8, "thumbnail_score": 7.5}, hook_drop=0.15),
        _row(tier="C", scores={"idea_score": 7.0, "thumbnail_score": 7.0}, hook_drop=0.25),
        _row(tier="D", scores={"idea_score": 6.0, "thumbnail_score": 6.5}, hook_drop=0.30),
        _row(tier="D", scores={"idea_score": 5.5, "thumbnail_score": 5.5}, hook_drop=0.35),
    ]
    by_dim, _ = _samples_by_dimension(rows)
    assert "idea_score" not in DIM_TO_RETENTION_FEATURE
    for s in by_dim.get("idea_score", []):
        assert s.retention_label is None




def _samples_with_retention(specs: list[tuple[float, bool | None]]) -> list[Sample]:
    """Build samples from (score, retention_label) pairs.

    Tier is set to a neutral 'B' for all rows so any test failure must
    come from the retention path, not tier leakage. A sentinel 'S' is
    inserted at the top of the score range so the monotonicity guard
    has an anchor.
    """
    out = [Sample(score=s, tier="B", retention_label=lab) for s, lab in specs]
    out.append(Sample(score=max(s for s, _ in specs) + 0.5, tier="S",
                      retention_label=True))
    return out


def test_calibrator_uses_retention_labels_when_available():
    """Reproduce Phase 7 lowest-acceptable test, but with retention
    labels driving win/flop instead of tier."""
    specs = (
        [(s, True)  for s in [8.0, 8.2, 8.4, 8.6, 8.8, 9.0, 8.1, 8.3, 8.5]]
        + [(s, False) for s in [
            5.0, 5.2, 5.5, 5.8, 6.0, 6.2, 6.4, 6.5,
            6.6, 6.7, 6.8, 6.9, 7.0, 5.3, 6.1, 6.3,
        ]]
    )
    samples = _samples_with_retention(specs)
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.status == "auto"
    assert res.win_rate_at_floor is not None
    assert res.win_rate_at_floor >= 0.70
    assert res.floor <= 8.0


def test_calibrator_monotonicity_guard_still_uses_tier_S_anchor():
    """The safety guard ('never block proven winners') must remain
    tier-anchored, not retention-anchored. A video can have S-tier
    performance with mediocre hook retention — we still mustn't block
    its score."""
    samples = [
        Sample(score=7.2, tier="S", retention_label=False),
        *[Sample(score=s, tier="A", retention_label=True)
          for s in [8.0, 8.2, 8.4, 8.6, 8.8]],
        *[Sample(score=s, tier="D", retention_label=False)
          for s in [5.0, 5.5, 6.0, 6.5, 7.0, 5.5, 6.2, 6.7,
                    5.8, 6.1, 6.3, 6.6, 6.8, 5.4, 5.9]],
    ]
    res = calibrate_dimension("hook_retention_score", samples, default_floor=7.5)
    assert res.floor <= 7.2, (
        f"Monotonicity guard failed: floor={res.floor} would block an S-tier video"
    )
