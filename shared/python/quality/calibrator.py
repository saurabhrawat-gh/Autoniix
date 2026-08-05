"""Per-niche quality-gate threshold calibrator (Phase 7).

Closes the last static-threshold loop: the gate now learns its floors
from real outcomes instead of using hand-picked numbers in
``PRODUCTION_THRESHOLDS``.

Algorithm (per niche, per dimension):

1. Pull joined samples ``(score_value, performance_tier)`` from
   ``quality_gate_decisions`` ⋈ ``feedback_loop`` ⋈ ``channels``.
2. Label ``win = tier in {S, A}`` and ``flop = tier == D``.
3. For every candidate threshold ``t`` from the score distribution,
   compute:
     * ``win_rate_at_floor``  — P(win | score ≥ t)
     * ``s_tier_preserved``   — fraction of *S-tier* samples with score ≥ t
4. Pick the **lowest** ``t`` such that ``win_rate_at_floor ≥ TARGET_PRECISION``.
   Lowest-acceptable, not highest-precision: we don't want to needlessly
   block content that performs.
5. **Monotonicity guard** — clamp the chosen ``t`` so it never exceeds
   the *minimum S-tier score* in the sample. Without this guard a single
   noisy run could lock the gate above proven winners.
6. **Sanity clamp** — final value bounded to [5.0, 9.5].

The calibrator is stateless and pure — it takes samples in, returns a
``CalibrationResult`` out. The DB layer wraps it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

from quality.gate import PRODUCTION_THRESHOLDS

logger = structlog.get_logger()


MIN_SAMPLES = 20

TARGET_PRECISION = 0.70

ABSOLUTE_FLOOR = 5.0
ABSOLUTE_CEILING = 9.5

WIN_TIERS = {"S", "A"}
FLOP_TIERS = {"D"}


DIM_TO_RETENTION_FEATURE: dict[str, str] = {
    "hook_retention_score": "hook_dropoff_30s",
    "script_structure_score": "mid_video_decay",
}
RETENTION_LOWER_IS_BETTER = {"hook_dropoff_30s", "mid_video_decay"}


@dataclass
class Sample:
    """One joined row: a score and the tier the resulting video earned.

    Phase 9 added the optional ``retention_label`` override. When set
    (because we have a measured retention curve for this dim), it
    short-circuits the tier-based win/flop classification with one
    derived directly from audience behaviour. ``tier`` is still kept
    on the sample because the calibrator's monotonicity guard reads
    ``tier == 'S'`` to anchor "this video clearly performed, never
    block it" — that safety property must hold regardless of curve
    shape (a video can have great views and a mediocre hook curve).
    """

    score: float
    tier: str
    retention_label: bool | None = None

    @property
    def is_win(self) -> bool:
        if self.retention_label is True:
            return True
        if self.retention_label is False:
            return False
        return self.tier in WIN_TIERS

    @property
    def is_flop(self) -> bool:
        if self.retention_label is False:
            return True
        if self.retention_label is True:
            return False
        return self.tier in FLOP_TIERS


@dataclass
class CalibrationResult:
    dimension: str
    floor: float
    n_samples: int
    win_rate_at_floor: float | None
    s_tier_preserved: float | None
    status: str = "auto"
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "floor": round(self.floor, 2),
            "n_samples": self.n_samples,
            "win_rate_at_floor": (round(self.win_rate_at_floor, 4) if self.win_rate_at_floor is not None else None),
            "s_tier_preserved": (round(self.s_tier_preserved, 4) if self.s_tier_preserved is not None else None),
            "status": self.status,
            "note": self.note,
        }


def _candidate_thresholds(samples: list[Sample]) -> list[float]:
    """Discrete grid of thresholds to evaluate.

    Using observed scores rounded to 0.1 keeps the grid small (≤50
    points typically) while still finding boundaries between adjacent
    samples. Sorted ascending.
    """
    grid = {round(s.score, 1) for s in samples}
    grid.add(ABSOLUTE_FLOOR)
    return sorted(grid)


def calibrate_dimension(
    dimension: str,
    samples: list[Sample],
    *,
    default_floor: float,
) -> CalibrationResult:
    """Find the best floor for one dimension on one niche.

    Always returns a result. When data is insufficient the result carries
    the existing ``default_floor`` and ``status = 'insufficient_samples'``.
    """
    n = len(samples)
    if n < MIN_SAMPLES:
        return CalibrationResult(
            dimension=dimension,
            floor=default_floor,
            n_samples=n,
            win_rate_at_floor=None,
            s_tier_preserved=None,
            status="insufficient_samples",
            note=f"need {MIN_SAMPLES}, got {n}",
        )

    wins = [s for s in samples if s.is_win]
    flops = [s for s in samples if s.is_flop]

    if not wins or not flops:
        return CalibrationResult(
            dimension=dimension,
            floor=default_floor,
            n_samples=n,
            win_rate_at_floor=None,
            s_tier_preserved=None,
            status="insufficient_samples",
            note=f"wins={len(wins)} flops={len(flops)} (need ≥1 each)",
        )

    s_tier = [s for s in samples if s.tier == "S"]
    min_s_tier_score = min(s.score for s in s_tier) if s_tier else None

    best: tuple[float, float, float] | None = None
    for t in _candidate_thresholds(samples):
        passing = [s for s in samples if s.score >= t]
        if not passing:
            continue
        n_wins_pass = sum(1 for s in passing if s.is_win)
        precision = n_wins_pass / len(passing)
        if precision < TARGET_PRECISION:
            continue
        s_preserved = sum(1 for s in s_tier if s.score >= t) / len(s_tier) if s_tier else 1.0
        best = (t, precision, s_preserved)
        break

    if best is None:
        return CalibrationResult(
            dimension=dimension,
            floor=default_floor,
            n_samples=n,
            win_rate_at_floor=None,
            s_tier_preserved=None,
            status="no_threshold_meets_precision",
            note=f"no threshold reaches {TARGET_PRECISION:.0%} precision",
        )

    t, precision, s_preserved = best

    if min_s_tier_score is not None and t > min_s_tier_score:
        t = min_s_tier_score
        passing = [s for s in samples if s.score >= t]
        if passing:
            precision = sum(1 for s in passing if s.is_win) / len(passing)
            s_preserved = sum(1 for s in s_tier if s.score >= t) / len(s_tier) if s_tier else 1.0

    floor = max(ABSOLUTE_FLOOR, min(ABSOLUTE_CEILING, t))

    return CalibrationResult(
        dimension=dimension,
        floor=floor,
        n_samples=n,
        win_rate_at_floor=precision,
        s_tier_preserved=s_preserved,
        status="auto",
        note="",
    )


def calibrate_all_dimensions(
    samples_by_dim: dict[str, list[Sample]],
) -> list[CalibrationResult]:
    """Convenience wrapper over every threshold-bearing dimension."""
    out = []
    for dim, default in PRODUCTION_THRESHOLDS.items():
        if dim == "composite_score":
            continue
        out.append(calibrate_dimension(dim, samples_by_dim.get(dim, []), default_floor=default))
    return out


def calibrate_composite(samples: list[Sample]) -> CalibrationResult:
    """Calibrate the composite_score threshold.

    Caller is responsible for computing each sample's composite via
    :func:`quality.gate._composite` from the stored sub_scores. We
    just calibrate over the resulting numbers like any other dimension.
    """
    return calibrate_dimension(
        "composite_score",
        samples,
        default_floor=PRODUCTION_THRESHOLDS["composite_score"],
    )


async def _fetch_samples_for_niche(niche: str, lookback_days: int = 90) -> list[dict]:
    """Pull joined gate decisions ⋈ feedback_loop ⋈ retention_curves.

    Phase 7 returned only ``(sub_scores, composite_score, tier)``.
    Phase 9 adds a LEFT JOIN against ``retention_curves`` so each
    sample can carry its measured curve features when available — and
    fall through to tier-based labelling when not. Videos with no
    curve row (typical for the first ~7 days post-publish, or any
    video where the YT Analytics fetch hasn't run yet) appear with
    NULL retention features and the calibrator silently uses tier.
    """
    from core.db import get_pool

    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT qgd.sub_scores, qgd.composite_score, fl.performance_tier,
               rc.hook_dropoff_30s, rc.mid_video_decay, rc.end_retention
        FROM quality_gate_decisions qgd
        JOIN      feedback_loop    fl ON fl.video_id   = qgd.content_id
        JOIN      channels         c  ON c.channel_id  = qgd.channel_id
        LEFT JOIN retention_curves rc ON rc.video_id   = qgd.content_id
        WHERE c.niche = $1
          AND fl.performance_tier IS NOT NULL
          AND qgd.created_at > NOW() - INTERVAL '%d days'
        """
        % int(lookback_days),
        niche,
    )
    return [dict(r) for r in rows]


def _niche_median(values: list[float]) -> float | None:
    """Median of a list of floats, ignoring None. Returns None if the
    list has fewer than 5 valid values — too few to trust as a niche-
    relative threshold, in which case we fall back to tier labels."""
    cleaned = sorted(v for v in values if v is not None)
    if len(cleaned) < 5:
        return None
    n = len(cleaned)
    if n % 2 == 1:
        return cleaned[n // 2]
    return (cleaned[n // 2 - 1] + cleaned[n // 2]) / 2.0


def _classify_by_retention(
    feature_value: float | None,
    median: float | None,
    *,
    lower_is_better: bool,
) -> bool | None:
    """Map a measured feature value → win (True) / flop (False) / unknown (None).

    Uses niche-relative split at the median. Samples *at* the median are
    treated as unknown (fall back to tier) — this avoids labelling
    half the population as wins and half as flops just because they
    happened to land on the boundary.
    """
    if feature_value is None or median is None:
        return None
    if abs(feature_value - median) < 1e-9:
        return None
    if lower_is_better:
        return feature_value < median
    return feature_value > median


def _samples_by_dimension(rows: list[dict]) -> tuple[dict[str, list[Sample]], list[Sample]]:
    """Convert raw rows → per-dim samples + composite samples.

    Returns ``(by_dim, composite)``. Rows with missing tiers are skipped
    upstream; here we only worry about score parsing.

    Phase 9: for the dimensions in ``DIM_TO_RETENTION_FEATURE``, apply
    a *measured* win/flop label derived from the audience-retention
    curve. Niche-median split keeps the win/flop balance stable across
    niches with very different absolute retention norms. When a row
    lacks the relevant curve feature, the sample falls through to the
    tier-based label exactly as in Phase 7.
    """
    retention_medians: dict[str, float | None] = {
        feature: _niche_median([r.get(feature) for r in rows]) for feature in set(DIM_TO_RETENTION_FEATURE.values())
    }

    by_dim: dict[str, list[Sample]] = {dim: [] for dim in PRODUCTION_THRESHOLDS if dim != "composite_score"}
    composite: list[Sample] = []
    for r in rows:
        tier = (r.get("performance_tier") or "").strip().upper()
        if tier not in WIN_TIERS and tier not in FLOP_TIERS and tier not in {"B", "C"}:
            continue
        sub = r.get("sub_scores") or {}
        if isinstance(sub, str):
            try:
                sub = json.loads(sub)
            except Exception:
                sub = {}
        for dim in by_dim:
            v = sub.get(dim)
            if v is None:
                continue
            try:
                score = float(v)
            except (TypeError, ValueError):
                continue
            retention_label: bool | None = None
            feature = DIM_TO_RETENTION_FEATURE.get(dim)
            if feature is not None:
                feat_value = r.get(feature)
                if feat_value is not None:
                    try:
                        feat_value = float(feat_value)
                    except (TypeError, ValueError):
                        feat_value = None
                retention_label = _classify_by_retention(
                    feat_value,
                    retention_medians.get(feature),
                    lower_is_better=feature in RETENTION_LOWER_IS_BETTER,
                )
            by_dim[dim].append(
                Sample(
                    score=score,
                    tier=tier,
                    retention_label=retention_label,
                )
            )
        comp = r.get("composite_score")
        if comp is not None:
            try:
                composite.append(Sample(score=float(comp), tier=tier))
            except (TypeError, ValueError):
                pass
    return by_dim, composite


async def calibrate_niche(niche: str) -> list[CalibrationResult]:
    """Calibrate every dimension for one niche and persist results.

    Idempotent: re-running with no new data produces the same rows.
    """
    rows = await _fetch_samples_for_niche(niche)
    by_dim, composite = _samples_by_dimension(rows)

    results = calibrate_all_dimensions(by_dim)
    results.append(calibrate_composite(composite))

    from core.db import get_pool

    pool = await get_pool()
    for r in results:
        await pool.execute(
            """
            INSERT INTO gate_thresholds (
                niche, dimension, floor, n_samples,
                win_rate_at_floor, s_tier_preserved, source, last_calibrated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (niche, dimension) DO UPDATE SET
                floor              = EXCLUDED.floor,
                n_samples          = EXCLUDED.n_samples,
                win_rate_at_floor  = EXCLUDED.win_rate_at_floor,
                s_tier_preserved   = EXCLUDED.s_tier_preserved,
                source             = EXCLUDED.source,
                last_calibrated_at = NOW()
            """,
            niche,
            r.dimension,
            float(r.floor),
            int(r.n_samples),
            float(r.win_rate_at_floor) if r.win_rate_at_floor is not None else None,
            float(r.s_tier_preserved) if r.s_tier_preserved is not None else None,
            "default" if r.status == "insufficient_samples" else "auto",
        )

    logger.info(
        "gate.calibrated",
        niche=niche,
        dims=len(results),
        auto=sum(1 for r in results if r.status == "auto"),
        insufficient=sum(1 for r in results if r.status == "insufficient_samples"),
    )
    return results


async def load_thresholds_for_niche(niche: str) -> dict[str, float]:
    """Live thresholds for the evaluator, with static-default fallback.

    Always returns a complete dict with every key in
    ``PRODUCTION_THRESHOLDS`` populated, so the evaluator never has to
    null-handle.
    """
    out = dict(PRODUCTION_THRESHOLDS)
    try:
        from core.db import get_pool

        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT dimension, floor FROM gate_thresholds WHERE niche = $1",
            niche,
        )
        for r in rows:
            dim = r["dimension"]
            if dim in out:
                out[dim] = float(r["floor"])
    except Exception as exc:
        logger.warning("gate.load_thresholds_failed", niche=niche, error=str(exc))
    return out
