"""GateCalibrationWorkflow — weekly per-niche quality-gate tuning.

Ported from ``go-workflows/gate_calibration.go``. Task queue: ``scheduler-v2``.
Cron: weekly Sunday 04:00 UTC.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

from .types import RETRY_LIGHT


@workflow.defn(name="GateCalibrationWorkflow")
class GateCalibrationWorkflow:
    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        log = workflow.logger

        niches: list[str] = await workflow.execute_activity(
            "list_niches_with_outcomes",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_LIGHT,
        )

        results: dict[str, Any] = {}
        for niche in niches:
            try:
                niche_result = await workflow.execute_activity(
                    "calibrate_gate_for_niche",
                    niche,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_LIGHT,
                )
                results[niche] = niche_result
            except Exception as exc:  # noqa: BLE001 — mirror Go's log.Warn + continue
                log.warn(
                    "calibrate_gate_for_niche failed",
                    extra={"niche": niche, "error": str(exc)},
                )
                results[niche] = {"action": "error", "error": str(exc)}

        return {"niches_processed": len(niches), "results": results}
