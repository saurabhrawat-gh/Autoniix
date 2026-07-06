"""Phase 9 — retention-curve feature extractor tests.

Locks the math that turns a YouTube Analytics ``audienceWatchRatio``
curve into the three diagnostic features the calibrator consumes
(``hook_dropoff_30s``, ``mid_video_decay``, ``end_retention``).
"""
from __future__ import annotations

import math

import pytest

from quality.retention_features import (
    CurvePoint,
    RetentionFeatures,
    compute_features,
    parse_curve,
)




def _flat_curve(value: float, n: int = 20) -> list[CurvePoint]:
    """Curve with constant watch_ratio for easy reasoning about features."""
    return [CurvePoint(elapsed_ratio=i / (n - 1), watch_ratio=value) for i in range(n)]


def _linear_decay(start: float, end: float, n: int = 20) -> list[CurvePoint]:
    """Curve linearly decaying from ``start`` to ``end``."""
    return [
        CurvePoint(
            elapsed_ratio=i / (n - 1),
            watch_ratio=start + (end - start) * i / (n - 1),
        )
        for i in range(n)
    ]




def test_parse_curve_accepts_pairs():
    raw = [[0.0, 1.0], [0.5, 0.7], [1.0, 0.3]]
    out = parse_curve(raw)
    assert len(out) == 3
    assert out[0].elapsed_ratio == 0.0
    assert out[2].watch_ratio == 0.3


def test_parse_curve_accepts_yt_field_names():
    raw = [
        {"elapsedVideoTimeRatio": 0.0, "audienceWatchRatio": 1.0},
        {"elapsedVideoTimeRatio": 0.5, "audienceWatchRatio": 0.6},
    ]
    out = parse_curve(raw)
    assert len(out) == 2
    assert out[1].watch_ratio == pytest.approx(0.6)


def test_parse_curve_drops_malformed_silently():
    raw = [
        [0.0, 1.0],
        {"elapsed_ratio": "garbage", "watch_ratio": 0.5},
        None,
        [0.5, 0.7],
    ]
    out = parse_curve(raw)
    assert len(out) == 2
    assert all(isinstance(p, CurvePoint) for p in out)


def test_parse_curve_sorts_by_elapsed():
    raw = [[0.5, 0.7], [0.0, 1.0], [1.0, 0.3]]
    out = parse_curve(raw)
    assert [p.elapsed_ratio for p in out] == [0.0, 0.5, 1.0]




def test_compute_features_too_sparse_returns_invalid():
    curve = _flat_curve(0.8, n=3)
    f = compute_features(curve, duration_seconds=120)
    assert f.valid is False
    assert f.hook_dropoff_30s is None
    assert f.mid_video_decay is None
    assert f.end_retention is None


def test_compute_features_no_duration_still_returns_end_retention():
    """Duration is needed for hook/mid features but not end retention."""
    curve = _flat_curve(0.6)
    f = compute_features(curve, duration_seconds=None)
    assert f.valid is True
    assert f.hook_dropoff_30s is None
    assert f.mid_video_decay is None
    assert f.end_retention == pytest.approx(0.6, abs=0.01)




def test_hook_dropoff_zero_for_perfect_retention():
    curve = _flat_curve(1.0)
    f = compute_features(curve, duration_seconds=60)
    assert f.hook_dropoff_30s == pytest.approx(0.0, abs=0.001)


def test_hook_dropoff_high_when_steep_initial_drop():
    """Curve drops from 1.0 at t=0 to 0.5 at t=0.5 (the 30s mark of a 60s video)."""
    curve = _linear_decay(1.0, 0.5)
    f = compute_features(curve, duration_seconds=60)
    assert f.hook_dropoff_30s == pytest.approx(0.25, abs=0.02)


def test_hook_dropoff_clamped_to_zero_for_increasing_curves():
    """YT can sometimes report watch_ratio > 1 for re-watches; we
    clamp the resulting dropoff to ≥ 0 so we never penalise a video
    for *gaining* viewers in the first 30s."""
    curve = [CurvePoint(0.0, 1.0)] + _flat_curve(1.05, n=19)
    curve = sorted(curve, key=lambda p: p.elapsed_ratio)
    f = compute_features(curve, duration_seconds=120)
    assert f.hook_dropoff_30s is not None
    assert f.hook_dropoff_30s == 0.0




def test_mid_decay_zero_for_flat_middle():
    curve = _flat_curve(0.7)
    f = compute_features(curve, duration_seconds=120)
    assert f.mid_video_decay == pytest.approx(0.0, abs=0.001)


def test_mid_decay_positive_for_decaying_middle():
    """Linear decay 1.0 → 0.0 over [0,1]. For a 120s video:
       30s mark is at elapsed=0.25, watch=0.75
       60% mark is at elapsed=0.6,  watch=0.4
       Mid decay ≈ 0.75 - 0.4 = 0.35.
    """
    curve = _linear_decay(1.0, 0.0)
    f = compute_features(curve, duration_seconds=120)
    assert f.mid_video_decay == pytest.approx(0.35, abs=0.05)


def test_mid_decay_none_for_short_video_where_30s_past_60pct():
    """A 40s video: 30s mark is at elapsed=0.75, past the 60% mark.
    Mid decay is ill-defined here — return None for that feature only."""
    curve = _flat_curve(0.5)
    f = compute_features(curve, duration_seconds=40)
    assert f.mid_video_decay is None
    assert f.hook_dropoff_30s is not None
    assert f.end_retention is not None




def test_end_retention_averages_last_20pct():
    """End retention = trapezoidal mean of watch_ratio over [0.8, 1.0]."""
    curve = _linear_decay(1.0, 0.0)
    f = compute_features(curve, duration_seconds=120)
    assert f.end_retention == pytest.approx(0.1, abs=0.02)


def test_end_retention_uses_last_segment_not_endpoint():
    """If the very last point dips, end_retention should still reflect
    the *average* across [0.8, 1.0], not just the last value."""
    curve = [CurvePoint(i / 19, 0.5) for i in range(19)]
    curve.append(CurvePoint(1.0, 0.0))
    f = compute_features(curve, duration_seconds=120)
    assert f.end_retention is not None
    assert 0.4 < f.end_retention < 0.5




def test_features_are_serializable_floats_or_none():
    """The persistence layer expects numeric or NULL — never NaN or inf."""
    curve = _linear_decay(1.0, 0.3)
    f = compute_features(curve, duration_seconds=120)
    for value in (f.hook_dropoff_30s, f.mid_video_decay, f.end_retention):
        assert value is None or isinstance(value, float)
        if value is not None:
            assert math.isfinite(value)
            assert 0.0 <= value <= 1.0
