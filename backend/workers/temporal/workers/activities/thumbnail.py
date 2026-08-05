from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def thumbnail_activity(params: dict) -> dict:
    """Call the Thumbnail Service to generate a YouTube thumbnail."""
    logger.info("activity.thumbnail.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post("http://thumbnail:8005/generate-thumbnail", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Thumbnail service returned {response.status_code}: {response.text[:500]}")
        return response.json()
