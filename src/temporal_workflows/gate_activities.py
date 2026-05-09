"""Activities for the GateCalibrationWorkflow.

Kept separate from ``model_activities`` so the worker registration list
in ``run_scheduler.py`` makes the new surface obvious. These two
activities are the only DB-touching code paths the calibration workflow
needs; the heavy lifting lives in :mod:`src.quality.calibrator`.
"""
from __future__ import annotations

from temporalio import activity

from src.db import get_pool
from src.quality.calibrator import calibrate_niche


@activity.defn(name="list_niches_with_outcomes")
async def list_niches_with_outcomes_activity() -> list[str]:
    """Return the distinct niches that have ≥1 measured outcome.

    Anything else has nothing to teach the calibrator, so we skip it
    silently. ``performance_tier IS NOT NULL`` is the cheapest filter
    that reflects "analytics has classified this video".
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT c.niche
        FROM channels c
        JOIN feedback_loop fl ON fl.channel_id = c.channel_id
        WHERE fl.performance_tier IS NOT NULL
          AND c.niche IS NOT NULL AND c.niche <> ''
        """
    )
    return [r["niche"] for r in rows]


@activity.defn(name="calibrate_gate_for_niche")
async def calibrate_gate_for_niche_activity(niche: str) -> dict:
    """Calibrate every gate dimension for one niche and persist.

    Returns a serialisable summary the workflow can log. Heavy lifting
    is delegated to :func:`src.quality.calibrator.calibrate_niche` so
    the activity stays a thin shell.
    """
    results = await calibrate_niche(niche)
    auto = sum(1 for r in results if r.status == "auto")
    insufficient = sum(1 for r in results if r.status == "insufficient_samples")
    no_threshold = sum(1 for r in results if r.status == "no_threshold_meets_precision")
    return {
        "niche": niche,
        "dims_total":        len(results),
        "dims_auto":         auto,
        "dims_insufficient": insufficient,
        "dims_no_threshold": no_threshold,
        "details":           [r.as_dict() for r in results],
    }
