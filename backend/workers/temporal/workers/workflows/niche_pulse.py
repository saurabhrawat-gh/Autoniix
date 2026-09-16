"""NichePulseRefreshWorkflow — weekly per-niche competitor snapshot refresh.

Ported from ``go-workflows/niche_pulse.go``. Task queue: ``scheduler-v2``.
Cron: weekly Sunday 05:00 UTC.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

from .types import RETRY_LIGHT


@workflow.defn(name="NichePulseRefreshWorkflow")
class NichePulseRefreshWorkflow:
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
                summary = await workflow.execute_activity(
                    "refresh_niche_pulse",
                    niche,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_LIGHT,
                )
                results[niche] = summary
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "refresh_niche_pulse failed",
                    extra={"niche": niche, "error": str(exc)},
                )
                results[niche] = {"action": "error", "error": str(exc)}

        return {"niches_processed": len(niches), "results": results}
