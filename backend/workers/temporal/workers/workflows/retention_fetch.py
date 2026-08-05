"""RetentionFetchWorkflow — daily audience-retention batch pull.

Ported from ``go-workflows/retention_fetch.go``. Task queue: ``scheduler-v2``.
Cron: daily 03:00 UTC.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from temporalio import workflow

from .types import RETRY_LIGHT

_DEFAULT_BATCH_LIMIT = 50


@workflow.defn(name="RetentionFetchWorkflow")
class RetentionFetchWorkflow:
    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        log = workflow.logger

        limit = _DEFAULT_BATCH_LIMIT
        if params and isinstance(params.get("limit"), (int, float)):
            limit = int(params["limit"])

        content_ids: list[str] = await workflow.execute_activity(
            "list_videos_needing_retention",
            limit,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_LIGHT,
        )

        status_counts: Counter[str] = Counter()
        for content_id in content_ids:
            try:
                summary = await workflow.execute_activity(
                    "fetch_retention_for_video",
                    content_id,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_LIGHT,
                )
                status = summary.get("status", "unknown") if isinstance(summary, dict) else "unknown"
                status_counts[status] += 1
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "fetch_retention_for_video failed",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                status_counts["error"] += 1

        return {
            "candidates": len(content_ids),
            "by_status": dict(status_counts),
        }
