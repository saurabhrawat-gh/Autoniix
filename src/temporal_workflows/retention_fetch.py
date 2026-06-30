"""Retention-curve fetch workflow (Phase 9).

For every delivered video aged 7-30 days that doesn't have a curve yet,
pull the audience-retention curve from YouTube Analytics and persist
the derived features (``hook_dropoff_30s``, ``mid_video_decay``,
``end_retention``).

The 7-30 day window is deliberate:

* **< 7 days**: the algorithm is still finding the audience; curves are
  unstable. Pulling earlier means training the calibrator on noisy
  labels.
* **> 30 days**: the curve has settled. Re-fetching adds little signal
  and consumes API quota.

Cron: daily 03:00 UTC. The Phase 7 calibrator runs Sunday 04:00 UTC,
so by the time it pulls samples the curves are populated.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


RETRY_LIGHT = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
)


DEFAULT_BATCH_LIMIT = 50


@workflow.defn
class RetentionFetchWorkflow:
    """Daily batched retention-curve fetch."""

    @workflow.run
    async def run(self, params: dict | None = None) -> dict:
        params = params or {}
        limit = int(params.get("limit", DEFAULT_BATCH_LIMIT))

        content_ids: list[str] = await workflow.execute_activity(
            "list_videos_needing_retention",
            args=[limit],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_LIGHT,
        )

        results: list[dict] = []
        for content_id in content_ids:
            try:
                summary = await workflow.execute_activity(
                    "fetch_retention_for_video",
                    args=[content_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_LIGHT,
                )
                results.append(summary)
            except Exception as exc:
                results.append({
                    "content_id": content_id,
                    "status":     "error",
                    "error":      str(exc),
                })

        status_counts: dict[str, int] = {}
        for r in results:
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "candidates": len(content_ids),
            "by_status":  status_counts,
        }
