from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

logger = structlog.get_logger()


class AssemblyRequest(BaseModel):
    content_id: str
    channel_id: str
    content_mode: str = "long_form"
    title: str
    script: dict = Field(default_factory=dict)
    voice_result: dict = Field(default_factory=dict)
    asset_manifest: dict = Field(default_factory=dict)
    thumbnail_result: dict = Field(default_factory=dict)
    brand_config: dict = Field(default_factory=dict)


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


def build_direction_v3(req: AssemblyRequest) -> dict:
    """Transform script + assets + voice into Remotion Direction v3 JSON."""
    segments = req.script.get("segments", [])
    manifest_items = {m["segment_id"]: m for m in req.asset_manifest.get("manifest", [])}

    aspect = "16:9" if req.content_mode == "long_form" else "9:16"
    resolution = {"width": 1920, "height": 1080} if req.content_mode == "long_form" else {"width": 1080, "height": 1920}
    fps = 30

    # Build Remotion segments
    remotion_segments = []
    cumulative_ms = 0

    for seg in segments:
        seg_id = seg.get("id", "s0")
        duration_s = seg.get("duration_s", 30)
        duration_ms = duration_s * 1000
        narration = seg.get("narration", "")
        direction = seg.get("scene_direction", "")
        text_overlay = seg.get("text_overlay", "")
        transition = seg.get("transition", "cut")

        # Get assets for this segment
        seg_assets = manifest_items.get(seg_id, {}).get("assets", [])
        bg_url = seg_assets[0]["url"] if seg_assets else ""

        remotion_seg = {
            "id": seg_id,
            "start_ms": cumulative_ms,
            "duration_ms": duration_ms,
            "scene_preset": "scene.stock_footage" if bg_url else "scene.kinetic_typography",
            "scene_overrides": {
                "background_url": bg_url,
                "label": text_overlay or "",
            },
            "narration": {
                "text": narration,
                "word_count": len(narration.split()),
            },
            "transition_in": {
                "preset": f"trans.{transition}" if transition != "cut" else "trans.cut",
                "duration_ms": 500,
            },
        }
        remotion_segments.append(remotion_seg)
        cumulative_ms += duration_ms

    # Compute total duration
    total_duration_s = cumulative_ms / 1000

    brand = req.brand_config or {}

    direction_v3 = {
        "version": "3.0",
        "meta": {
            "video_id": req.content_id,
            "channel_id": req.channel_id,
            "title": req.title,
            "duration_target_seconds": total_duration_s,
            "aspect": aspect,
            "fps": fps,
            "resolution": resolution,
        },
        "template": brand.get("template", "hybrid-kinetic"),
        "theme": {
            "primary_color": brand.get("primary_color", "#FF3B30"),
            "accent_color": brand.get("accent_color", "#FFD60A"),
            "background_color": brand.get("background_color", "#000000"),
            "text_color": brand.get("text_color", "#FFFFFF"),
            "fonts": brand.get("fonts", {"heading": "Inter", "body": "Inter"}),
        },
        "grade_preset": brand.get("grade_preset", "fx.grade.cinematic_teal_orange"),
        "global_overlays": [
            {"type": "vignette", "intensity": 0.3},
            {"type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15},
        ],
        "audio_master": {
            "narration_url": req.voice_result.get("audio_url", ""),
            "music_url": "",
            "music_volume": 0.15,
            "ducking": True,
            "ducking_threshold": -20,
        },
        "segments": remotion_segments,
    }

    return direction_v3


@app.post("/assemble", response_model=ServiceResponse)
async def assemble(req: AssemblyRequest):
    logger.info("assembly.assembling", content_id=req.content_id)

    try:
        direction_v3 = build_direction_v3(req)

        # Store in database
        try:
            pool = await get_pool()
            import json
            await pool.execute(
                "UPDATE videos SET v3_direction = $1, updated_at = NOW() WHERE content_id = $2",
                json.dumps(direction_v3),
                req.content_id,
            )
        except Exception as e:
            logger.warning("assembly.db_update_failed", error=str(e))

        logger.info(
            "assembly.completed",
            segments=len(direction_v3["segments"]),
            duration=direction_v3["meta"]["duration_target_seconds"],
        )

        return ServiceResponse(
            status="success",
            data={
                "direction_v3": direction_v3,
                "segment_count": len(direction_v3["segments"]),
                "total_duration_s": direction_v3["meta"]["duration_target_seconds"],
            },
            cost={"cost_usd": 0, "provider": "assembly"},
        )

    except Exception as exc:
        logger.error("assembly.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.assembly.main:app", host="0.0.0.0", port=8006, log_level="info")
