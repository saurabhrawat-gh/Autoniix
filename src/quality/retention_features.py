"""Curve → features (Phase 9).

The YouTube Analytics API ``audienceWatchRatio`` report returns a curve
of (elapsedVideoTimeRatio, audienceWatchRatio) pairs sampled at a
roughly 100-point grid. Both axes are in [0, 1]:

* ``elapsedVideoTimeRatio`` — fraction of the video duration elapsed
  (0 = start, 1 = end).
* ``audienceWatchRatio`` — fraction of viewers still watching at that
  moment relative to viewers at t=0. So 1.0 at t=0 means "everyone";
  0.45 at t=0.5 means "45% are still watching at the midpoint."

This module turns that raw curve into three diagnostic features:

* ``hook_dropoff_30s`` — how many viewers we lost in the first 30
  seconds. **Lower is better.** Direct ground truth for whether the
  hook is doing its job.
* ``mid_video_decay`` — retention drop between the 30s mark and the
  60% mark. **Lower is better.** Captures pacing/payoff problems
  after the hook earns the watch.
* ``end_retention`` — average audienceWatchRatio over the last 20%
  of the video. **Higher is better.** Captures whether the end is
  paying off the front-loaded promise.

These three features replace the noisy compound ``performance_tier``
label as the calibration target for the dimensions where they apply
(``hook_retention_score`` and ``script_structure_score``).

All math here is pure: no DB, no API calls. The wrapper that pulls
from YouTube Analytics lives in ``src/services/analytics/retention_fetcher``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable




@dataclass
class CurvePoint:
    """One sample on the audience-retention curve."""
    elapsed_ratio: float
    watch_ratio:   float


@dataclass
class RetentionFeatures:
    """The three derived features the Phase 9 calibrator consumes."""
    hook_dropoff_30s: float | None
    mid_video_decay:  float | None
    end_retention:    float | None
    valid:            bool




def _interpolate_at(curve: list[CurvePoint], at: float) -> float | None:
    """Linear interpolation of watch_ratio at a given elapsed_ratio.

    Returns None if the curve doesn't cover ``at`` (e.g. only 2 points
    at the extremes or curve is empty). The calibrator falls back to
    tier labels when this returns None — never invents data.
    """
    if not curve:
        return None
    if at <= curve[0].elapsed_ratio:
        return curve[0].watch_ratio
    if at >= curve[-1].elapsed_ratio:
        return curve[-1].watch_ratio
    lo, hi = 0, len(curve) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if curve[mid].elapsed_ratio <= at:
            lo = mid
        else:
            hi = mid
    p0, p1 = curve[lo], curve[hi]
    span = p1.elapsed_ratio - p0.elapsed_ratio
    if span <= 0:
        return p0.watch_ratio
    t = (at - p0.elapsed_ratio) / span
    return p0.watch_ratio + t * (p1.watch_ratio - p0.watch_ratio)


def _avg_over_range(curve: list[CurvePoint], lo: float, hi: float) -> float | None:
    """Mean watch_ratio across [lo, hi] in elapsed_ratio space.

    Uses trapezoidal integration over the curve points falling inside
    the range, plus interpolated endpoints. Returns None if the range
    has zero width or the curve doesn't reach into it at all.
    """
    if hi <= lo or not curve:
        return None
    seg: list[CurvePoint] = []
    lo_val = _interpolate_at(curve, lo)
    if lo_val is not None:
        seg.append(CurvePoint(lo, lo_val))
    for p in curve:
        if lo < p.elapsed_ratio < hi:
            seg.append(p)
    hi_val = _interpolate_at(curve, hi)
    if hi_val is not None:
        seg.append(CurvePoint(hi, hi_val))
    if len(seg) < 2:
        return None
    area = 0.0
    width = 0.0
    for a, b in zip(seg[:-1], seg[1:]):
        dx = b.elapsed_ratio - a.elapsed_ratio
        if dx <= 0:
            continue
        area += dx * (a.watch_ratio + b.watch_ratio) / 2.0
        width += dx
    if width <= 0:
        return None
    return area / width




def parse_curve(raw: Iterable) -> list[CurvePoint]:
    """Coerce a list of (elapsed, watch) pairs / dicts into ``CurvePoint``s.

    Accepts:
    * list of two-element sequences: ``[[0.0, 1.0], [0.1, 0.92], ...]``
    * list of dicts with 'elapsed_ratio' / 'watch_ratio' keys
    * list of dicts with 'elapsedVideoTimeRatio' / 'audienceWatchRatio'
      keys (the YT Analytics API field names)

    Anything malformed is silently dropped — robustness over strictness,
    because calibrator fallback is safe.
    """
    out: list[CurvePoint] = []
    for item in raw or []:
        try:
            if isinstance(item, dict):
                e = item.get("elapsed_ratio")
                if e is None:
                    e = item.get("elapsedVideoTimeRatio")
                w = item.get("watch_ratio")
                if w is None:
                    w = item.get("audienceWatchRatio")
            else:
                e, w = item[0], item[1]
            if e is None or w is None:
                continue
            out.append(CurvePoint(float(e), float(w)))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    out.sort(key=lambda p: p.elapsed_ratio)
    return out


def compute_features(
    curve: list[CurvePoint],
    duration_seconds: float | None = None,
) -> RetentionFeatures:
    """Derive the three Phase-9 features from a parsed curve.

    Args:
        curve: parsed curve, sorted by elapsed_ratio.
        duration_seconds: video length, used to map "30s" into
            elapsed_ratio space. If None or non-positive we can't compute
            ``hook_dropoff_30s`` or ``mid_video_decay`` because the 30s
            mark is undefined; only ``end_retention`` survives.

    Returns:
        RetentionFeatures with ``valid=False`` if the curve has fewer
        than 5 points (too sparse to trust). The calibrator treats
        invalid features as "no signal here, fall back to tier."
    """
    if len(curve) < 5:
        return RetentionFeatures(None, None, None, valid=False)

    end = _avg_over_range(curve, 0.80, 1.00)

    if duration_seconds is None or duration_seconds <= 0:
        return RetentionFeatures(None, None, end, valid=end is not None)

    t30 = max(0.0, min(1.0, 30.0 / duration_seconds))

    watch_at_30s = _interpolate_at(curve, t30)
    if watch_at_30s is None:
        return RetentionFeatures(None, None, end, valid=end is not None)

    watch_at_start = curve[0].watch_ratio if curve[0].elapsed_ratio < 1e-3 else 1.0
    if watch_at_start <= 0:
        watch_at_start = 1.0
    hook_drop = max(0.0, min(1.0, 1.0 - watch_at_30s / watch_at_start))

    if t30 >= 0.60:
        mid_decay = None
    else:
        watch_at_60 = _interpolate_at(curve, 0.60)
        if watch_at_60 is None:
            mid_decay = None
        else:
            r_30 = watch_at_30s / watch_at_start
            r_60 = watch_at_60 / watch_at_start
            mid_decay = max(0.0, r_30 - r_60)

    return RetentionFeatures(
        hook_dropoff_30s=round(hook_drop, 4),
        mid_video_decay=round(mid_decay, 4) if mid_decay is not None else None,
        end_retention=round(end, 4) if end is not None else None,
        valid=True,
    )
