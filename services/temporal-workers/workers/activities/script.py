from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def script_activity(params: dict) -> dict:
    """Call the Script Service to generate a full script."""
    logger.info("activity.script.started", channel_id=params.get("channel_id"))

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post("http://script:8002/generate-script", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Script service returned {response.status_code}: {response.text[:500]}")
        return response.json()


@activity.defn
async def title_activity(params: dict) -> dict:
    """Call the Script Service to generate titles."""
    logger.info("activity.title.started", topic=params.get("topic", "")[:50])

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://script:8002/generate-titles", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Script service returned {response.status_code}: {response.text[:500]}")
        return response.json()
