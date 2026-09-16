from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def direction_activity(params: dict) -> dict:
    """Call the Direction Service to generate per-segment visual direction + Remotion v3 JSON."""
    logger.info("activity.direction.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post("http://direction:8010/generate-direction", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Direction service returned {response.status_code}: {response.text[:500]}")
        return response.json()
