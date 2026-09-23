"""Activities for the RetentionFetchWorkflow (Phase 9)."""

from __future__ import annotations

from temporalio import activity


@activity.defn(name="list_videos_needing_retention")
async def list_videos_needing_retention_activity(limit: int) -> list[str]:
    """Find delivered videos in the curve-stable window without curves yet."""
    from services_api.analytics.retention_fetcher import videos_needing_retention

    return await videos_needing_retention(limit=limit)


@activity.defn(name="fetch_retention_for_video")
async def fetch_retention_for_video_activity(content_id: str) -> dict:
    """Fetch + persist the retention curve for one video."""
    from services_api.analytics.retention_fetcher import fetch_and_store_retention

    summary = await fetch_and_store_retention(content_id)
    summary["content_id"] = content_id
    return summary
