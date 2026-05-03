from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def brand_activity(params: dict) -> dict:
    """Call the Brand Identity Service."""
    action = params.get("action", "get_or_create")
    logger.info("activity.brand.started", channel_id=params.get("channel_id"), action=action)

    if action == "consistency":
        url = "http://brand:8012/consistency"
    elif action == "evolution":
        url = "http://brand:8012/evolution"
    else:
        url = "http://brand:8012/profile"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Brand service returned {response.status_code}: {response.text[:500]}")
        return response.json()
