from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def delivery_activity(params: dict) -> dict:
    """Call the Delivery Service to upload to YouTube."""
    logger.info("activity.delivery.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post("http://delivery:8007/upload", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Delivery service returned {response.status_code}: {response.text[:500]}")
        return response.json()
