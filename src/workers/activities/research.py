from __future__ import annotations

import httpx
import structlog
from temporalio import activity

from src.config import settings

logger = structlog.get_logger()

RESEARCH_URL = "http://research:8001/research"


@activity.defn
async def research_activity(params: dict) -> dict:
    """Call the Research Service HTTP endpoint."""
    logger.info("activity.research.started", channel_id=params.get("channel_id"))

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(RESEARCH_URL, json=params)

        if response.status_code != 200:
            detail = response.text[:500]
            raise RuntimeError(f"Research service returned {response.status_code}: {detail}")

        result = response.json()

    logger.info(
        "activity.research.completed",
        topic=result.get("data", {}).get("selected_topic"),
        cost=result.get("cost"),
    )
    return result
