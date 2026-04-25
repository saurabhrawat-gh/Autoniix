from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class AssemblyRequest(BaseModel):
    content_id: str
    channel_id: str
    content_mode: str = "short"
    title: str
    direction_v3: dict = Field(default_factory=dict)
    thumbnail_url: str = ""


class RenderStatusRequest(BaseModel):
    render_id: str


# ── Helpers ──────────────────────────────────────────────────

async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("assembly.starting")
    yield
    await close_pool()
    logger.info("assembly.stopped")


app = FastAPI(title="Assembly Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="assembly")


@app.post("/assemble", response_model=ServiceResponse)
async def assemble(req: AssemblyRequest):
    """Submit Direction v3 to Remotion API for rendering, poll until complete."""
    logger.info("assembly.assembling", content_id=req.content_id,
                 segments=len(req.direction_v3.get("segments", [])))

    try:
        direction_v3 = req.direction_v3
        if not direction_v3 or not direction_v3.get("segments"):
            raise HTTPException(status_code=400, detail="No direction_v3 data provided")

        # ── Step 1: Submit render job to Remotion API ────
        remotion_url = settings.remotion_base_url
        render_payload = {
            "direction": direction_v3,
            "outputFormat": "mp4",
            "quality": "high",
            "codec": "h264",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{remotion_url}/render", json=render_payload)
            resp.raise_for_status()
            render_data = resp.json()

        render_id = render_data.get("renderId", render_data.get("id", ""))
        if not render_id:
            raise HTTPException(status_code=500, detail="No render ID returned from Remotion")

        logger.info("assembly.render_submitted", render_id=render_id)

        # ── Step 2: Poll for render completion ───────────
        max_wait_s = 600  # 10 minutes max
        poll_interval_s = 5
        elapsed = 0
        render_result = None

        while elapsed < max_wait_s:
            await asyncio.sleep(poll_interval_s)
            elapsed += poll_interval_s

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    status_resp = await client.get(f"{remotion_url}/render/{render_id}")
                    status_resp.raise_for_status()
                    render_result = status_resp.json()

                status = render_result.get("status", "unknown")
                if status == "completed":
                    break
                elif status == "failed":
                    error_msg = render_result.get("error", "Unknown render error")
                    raise HTTPException(status_code=500, detail=f"Render failed: {error_msg}")
                else:
                    progress = render_result.get("progress", 0)
                    logger.info("assembly.render_progress", render_id=render_id,
                                 status=status, progress=progress, elapsed=elapsed)

            except httpx.HTTPError as poll_err:
                logger.warning("assembly.poll_error", error=str(poll_err))

        if not render_result or render_result.get("status") != "completed":
            raise HTTPException(status_code=504, detail="Render timed out after 10 minutes")

        video_url = render_result.get("outputUrl", render_result.get("url", ""))
        render_duration = render_result.get("renderDuration", 0)

        # ── Step 3: Production QC ────────────────────────
        production_score = 8.0
        production_issues = []

        target_duration = direction_v3.get("meta", {}).get("duration_target_seconds", 0)
        actual_duration = render_result.get("videoDuration", target_duration)
        if target_duration and abs(actual_duration - target_duration) > target_duration * 0.1:
            production_score -= 1.0
            production_issues.append(f"Duration mismatch: target {target_duration}s, actual {actual_duration}s")

        if not video_url:
            production_score -= 2.0
            production_issues.append("No output URL from render")

        # ── Step 4: Update DB ────────────────────────────
        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET render_url = $1, render_id = $2, production_score = $3, "
                "status = 'rendered', updated_at = NOW() WHERE content_id = $4",
                video_url, render_id, production_score, req.content_id)
        except Exception as e:
            logger.warning("assembly.db_update_failed", error=str(e))

        logger.info("assembly.completed",
                     render_id=render_id,
                     video_url=video_url[:80] if video_url else "",
                     production_score=production_score,
                     render_time=render_duration)

        return ServiceResponse(
            status="success",
            data={
                "render_id": render_id,
                "video_url": video_url,
                "render_duration_s": render_duration,
                "video_duration_s": actual_duration,
                "production_score": round(production_score, 1),
                "production_issues": production_issues,
                "segment_count": len(direction_v3.get("segments", [])),
            },
            cost={"cost_usd": 0, "provider": "remotion"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("assembly.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/render-status/{render_id}", response_model=ServiceResponse)
async def render_status(render_id: str):
    """Check the status of a Remotion render job."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.remotion_base_url}/render/{render_id}")
            resp.raise_for_status()
            return ServiceResponse(status="success", data=resp.json())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.assembly.main:app", host="0.0.0.0", port=8006, log_level="info")
