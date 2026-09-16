from __future__ import annotations

import httpx
import structlog
from temporalio import activity

logger = structlog.get_logger()


@activity.defn
async def editor_activity(params: dict) -> dict:
    """Call the Editor / Post-Production Service."""
    logger.info("activity.editor.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post("http://editor:8013/post-produce", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Editor service returned {response.status_code}: {response.text[:500]}")
        return response.json()
