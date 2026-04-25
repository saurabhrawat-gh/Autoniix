from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def analytics_activity(params: dict) -> dict:
    """Call the Analytics Service to collect YouTube stats."""
    logger.info("activity.analytics.started", channel_id=params.get("channel_id"))

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://analytics:8008/collect", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Analytics service returned {response.status_code}: {response.text[:500]}")
        return response.json()
