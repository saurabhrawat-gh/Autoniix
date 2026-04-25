from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def voice_activity(params: dict) -> dict:
    """Call the Voice Service to synthesize narration audio."""
    logger.info("activity.voice.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post("http://voice:8003/synthesize", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Voice service returned {response.status_code}: {response.text[:500]}")
        return response.json()
