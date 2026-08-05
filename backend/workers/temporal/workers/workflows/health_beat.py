"""HealthBeatWorkflow — invokes ``check_all_provider_health`` every 5 min.

Ported from ``go-workflows/health_beat.go``. Task queue: ``scheduler-v2``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow


@workflow.defn(name="HealthBeatWorkflow")
class HealthBeatWorkflow:
    @workflow.run
    async def run(self) -> dict[str, Any]:
        return await workflow.execute_activity(
            "check_all_provider_health",
            start_to_close_timeout=timedelta(minutes=4),
            schedule_to_close_timeout=timedelta(minutes=4),
        )
