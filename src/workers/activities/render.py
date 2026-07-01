from __future__ import annotations

import asyncio

import httpx
import structlog
from temporalio import activity

from src.config import settings

logger = structlog.get_logger()


@activity.defn
async def render_activity(params: dict) -> dict:
    """Call the Remotion render service to produce the final video.

    Flow: health check → submit render → poll until done.
    """
    base_url = settings.remotion_base_url
    content_id = params.get("content_id", "unknown")
    direction_v3 = params.get("direction_v3", {})

    logger.info("activity.render.started", content_id=content_id, base_url=base_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            health_resp = await client.get(f"{base_url}/api/health")
            health_data = health_resp.json()
            if health_data.get("status") != "healthy":
                raise RuntimeError(f"Remotion unhealthy: {health_data}")
            if health_data.get("activeRenders", 0) >= health_data.get("maxConcurrent", 3):
                raise RuntimeError("Remotion at capacity")
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot reach Remotion at {base_url}")

    async with httpx.AsyncClient(timeout=600.0) as client:
        render_body = {
            "composition": "MainVideo",
            "inputProps": {"direction": direction_v3},
            "codec": "h264",
            "outputFormat": "mp4",
            "quality": 80,
        }

        submit_resp = await client.post(f"{base_url}/api/render", json=render_body)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        render_id = submit_data.get("renderId", "")

        logger.info("activity.render.submitted", render_id=render_id)

        max_polls = 120
        for i in range(max_polls):
            activity.heartbeat(f"Polling render {render_id}: attempt {i+1}")
            await asyncio.sleep(30)

            status_resp = await client.get(f"{base_url}/api/render/{render_id}")
            status_data = status_resp.json()
            status = status_data.get("status", "")

            if status == "done":
                output_url = status_data.get("outputUrl", "")
                logger.info("activity.render.completed", render_id=render_id, output_url=output_url[:100])
                return {
                    "status": "success",
                    "data": {
                        "render_id": render_id,
                        "output_url": output_url,
                        "file_size": status_data.get("fileSize", 0),
                        "duration": status_data.get("duration", 0),
                    },
                    "cost": {"cost_usd": 0, "provider": "remotion"},
                }

            elif status == "failed":
                error = status_data.get("error", "Unknown render error")
                raise RuntimeError(f"Render failed: {error}")


        raise RuntimeError(f"Render timed out after {max_polls * 30}s")
