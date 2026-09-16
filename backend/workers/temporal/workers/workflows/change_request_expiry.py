"""ChangeRequestExpiryWorkflow — hourly cleanup of stale change requests.

Ported from ``go-workflows/change_request_expiry.go``. Task queue: ``scheduler-v2``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow


@workflow.defn(name="ChangeRequestExpiryWorkflow")
class ChangeRequestExpiryWorkflow:
    @workflow.run
    async def run(self) -> dict[str, Any]:
        return await workflow.execute_activity(
            "expire_stale_change_requests",
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=5),
        )
