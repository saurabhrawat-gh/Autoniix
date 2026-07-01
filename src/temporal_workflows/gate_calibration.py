"""Quality-gate threshold calibration workflow (Phase 7).

Runs weekly. For every distinct active niche:
  1. Pull joined gate decisions × feedback_loop tiers (last 90 days).
  2. Fit per-dimension thresholds via the calibrator.
  3. Persist results to ``gate_thresholds``.

Why a separate workflow rather than appending to ModelMaintenance:
the calibrator is the *only* component that needs to iterate over niches
rather than a fixed model list, so its workflow shape is different.
Keeping it standalone also means a regression in this loop can't break
the script/voice/thumbnail retrain cadence.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


RETRY_LIGHT = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)


@workflow.defn
class GateCalibrationWorkflow:
    """Weekly per-niche quality-gate threshold tuning."""

    @workflow.run
    async def run(self, params: dict | None = None) -> dict:
        niches: list[str] = await workflow.execute_activity(
            "list_niches_with_outcomes",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_LIGHT,
        )

        results: dict[str, dict] = {}
        for niche in niches:
            try:
                niche_result = await workflow.execute_activity(
                    "calibrate_gate_for_niche",
                    args=[niche],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_LIGHT,
                )
                results[niche] = niche_result
            except Exception as exc:
                results[niche] = {"action": "error", "error": str(exc)}

        return {"niches_processed": len(niches), "results": results}
