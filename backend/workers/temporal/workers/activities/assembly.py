from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def assembly_activity(params: dict) -> dict:
    """Call the Assembly Service to build Remotion Direction v3."""
    logger.info("activity.assembly.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://assembly:8006/assemble", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Assembly service returned {response.status_code}: {response.text[:500]}")
        return response.json()
