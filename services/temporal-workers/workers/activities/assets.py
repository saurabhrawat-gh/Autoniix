from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def assets_activity(params: dict) -> dict:
    """Call the Assets Service to generate scene images."""
    logger.info("activity.assets.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post("http://assets:8004/generate-assets", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Assets service returned {response.status_code}: {response.text[:500]}")
        return response.json()
