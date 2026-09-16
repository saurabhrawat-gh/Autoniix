from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def music_activity(params: dict) -> dict:
    """Call the Assets Service /search-music endpoint for background music + SFX."""
    logger.info("activity.music.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://assets:8004/search-music", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Music search returned {response.status_code}: {response.text[:500]}")
        return response.json()
