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


@activity.defn
async def compute_metadata_activity(params: dict) -> dict:
    """Call the Delivery Service to compute and store YouTube metadata without uploading.

    Used in test mode to populate delivery_result with SEO data.
    """
    logger.info("activity.compute_metadata.started", content_id=params.get("content_id"))

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://delivery:8007/compute-metadata", json=params)
        if response.status_code != 200:
            raise RuntimeError(f"Compute metadata returned {response.status_code}: {response.text[:500]}")
        return response.json()
