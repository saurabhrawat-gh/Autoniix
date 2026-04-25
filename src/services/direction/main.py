from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.llm.openai_provider  # noqa: F401
from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class DirectionRequest(BaseModel):
    content_id: str
    channel_id: str
    content_mode: str = "short"
    title: str
    script_segments: list[dict] = Field(default_factory=list)
    voice_manifest: dict = Field(default_factory=dict)
    asset_manifest: list[dict] = Field(default_factory=list)
    thumbnail_result: dict = Field(default_factory=dict)
    music_data: dict = Field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


async def _load_prompt(prompt_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT system_prompt, user_prompt_template FROM prompt_registry "
        "WHERE prompt_id = $1 AND is_active = true", prompt_id)
    return dict(row) if row else {}


async def _log_usage(content_id: str, service: str, provider: str, model: str,
                     tokens_in: int, tokens_out: int, cost: float, latency: int):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            content_id, service, provider, model, tokens_in, tokens_out, float(cost), latency)
    except Exception as e:
        logger.warning("direction.db_log_failed", error=str(e))


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("direction.starting")
    yield
    await close_pool()
    logger.info("direction.stopped")


app = FastAPI(title="Direction Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="direction")


@app.post("/generate-direction", response_model=ServiceResponse)
async def generate_direction(req: DirectionRequest):
    """Generate per-segment visual direction + Remotion v3 JSON from script + assets + voice."""
    logger.info("direction.generating", content_id=req.content_id, segments=len(req.script_segments))
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        is_long = req.content_mode == "long_form"
        aspect = "16:9" if is_long else "9:16"
        resolution = {"width": 1920, "height": 1080} if is_long else {"width": 1080, "height": 1920}
        fps = 30

        # Build asset lookup
        asset_lookup = {}
        for item in req.asset_manifest:
            seg_id = item.get("segment_id", "")
            asset_lookup[seg_id] = item

        # Build voice segment lookup
        segment_urls = req.voice_manifest.get("segment_urls", {})

        # ── Step 1: GPT Direction for each segment ───────
        prompt = await _load_prompt("PRM_B4_DIRECTION")
        direction_llm = ProviderRegistry.get("llm.direction")

        segments_summary = json.dumps([
            {
                "id": s.get("id"),
                "section": s.get("section"),
                "narration_preview": s.get("narration", "")[:100],
                "scene_direction": s.get("scene_direction", ""),
                "text_overlay": s.get("text_overlay", ""),
                "transition": s.get("transition", "cut"),
                "duration_s": s.get("duration_s", 10),
                "has_asset": s.get("id", "") in asset_lookup,
                "asset_type": asset_lookup.get(s.get("id", ""), {}).get("type", "none"),
            }
            for s in req.script_segments
        ], indent=2)[:4000]

        system_prompt = prompt.get("system_prompt",
            "Generate per-segment visual direction for Remotion rendering. Respond in JSON.").format(
            aspect=aspect,
            resolution=json.dumps(resolution),
        )
        user_prompt = prompt.get("user_prompt_template",
            "Segments: {segments}\nChannel style: {visual_style}").format(
            title=req.title,
            segments=segments_summary,
            visual_style=channel.get("visual_style", "cinematic"),
            thumbnail_style=channel.get("thumbnail_style", "bold_cinematic"),
            primary_color=channel.get("primary_color", "#1A237E"),
            accent_color=channel.get("accent_color", "#FF6F00"),
            template_preference=channel.get("remotion_template", "hybrid-kinetic"),
        )

        result = await direction_llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o",
            temperature=0.5,
            max_tokens=3000,
            response_format="json",
        ))
        total_cost += result.cost_usd
        await _log_usage(req.content_id, "direction", result.provider, result.model,
                         result.tokens_in, result.tokens_out, result.cost_usd, result.latency_ms)

        try:
            direction_data = _parse_json(result.content)
            gpt_segments = direction_data.get("segments", [])
        except json.JSONDecodeError:
            gpt_segments = []

        # ── Step 2: Build Remotion Direction v3 ──────────
        gpt_lookup = {s.get("id"): s for s in gpt_segments}
        remotion_segments = []
        cumulative_ms = 0

        for seg in req.script_segments:
            seg_id = seg.get("id", "s0")
            duration_s = seg.get("duration_s", 10)
            duration_ms = duration_s * 1000
            narration = seg.get("narration", "")
            text_overlay = seg.get("text_overlay", "")
            transition = seg.get("transition", "cut")

            # Get GPT direction for this segment
            gpt_dir = gpt_lookup.get(seg_id, {})

            # Get asset for this segment
            seg_asset = asset_lookup.get(seg_id, {})
            assets = seg_asset.get("assets", [])
            bg_url = assets[0]["url"] if assets else ""
            asset_type = seg_asset.get("type", "none")

            # Get voice audio for this segment
            voice_url = segment_urls.get(seg_id, "")

            # Determine scene preset from GPT or fallback
            scene_preset = gpt_dir.get("scene_preset", "")
            if not scene_preset:
                if asset_type == "stock_video":
                    scene_preset = "scene.stock_footage"
                elif asset_type == "generated_image":
                    scene_preset = "scene.ken_burns"
                else:
                    scene_preset = "scene.kinetic_typography"

            remotion_seg = {
                "id": seg_id,
                "start_ms": cumulative_ms,
                "duration_ms": duration_ms,
                "section": seg.get("section", "body"),
                "scene_preset": scene_preset,
                "scene_overrides": {
                    "background_url": bg_url,
                    "label": text_overlay,
                    "animation": gpt_dir.get("animation", "fade_in"),
                    "zoom_direction": gpt_dir.get("zoom_direction", ""),
                    "text_position": gpt_dir.get("text_position", "center"),
                    "emphasis_words": gpt_dir.get("emphasis_words", []),
                },
                "narration": {
                    "text": narration,
                    "word_count": len(narration.split()),
                    "audio_url": voice_url,
                },
                "transition_in": {
                    "preset": f"trans.{transition}" if transition != "cut" else "trans.cut",
                    "duration_ms": gpt_dir.get("transition_duration_ms", 500),
                },
                "visual_effects": gpt_dir.get("visual_effects", []),
            }
            remotion_segments.append(remotion_seg)
            cumulative_ms += duration_ms

        total_duration_s = cumulative_ms / 1000
        brand_primary = channel.get("primary_color", "#1A237E")
        brand_accent = channel.get("accent_color", "#FF6F00")

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
            "template": channel.get("remotion_template", "hybrid-kinetic"),
            "theme": {
                "primary_color": brand_primary,
                "accent_color": brand_accent,
                "background_color": channel.get("background_color", "#0A0A0A"),
                "text_color": channel.get("text_color", "#FFFFFF"),
                "fonts": {
                    "heading": channel.get("font_heading", "Inter"),
                    "body": channel.get("font_body", "Inter"),
                },
            },
            "grade_preset": channel.get("grade_preset", "fx.grade.cinematic_teal_orange"),
            "global_overlays": [
                {"type": "vignette", "intensity": 0.3},
                {"type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15},
            ],
            "audio_master": {
                "narration_url": req.voice_manifest.get("audio_url", ""),
                "music_url": req.music_data.get("music", [{}])[0].get("url", "") if req.music_data.get("music") else "",
                "music_volume": 0.15,
                "ducking": True,
                "ducking_threshold": -20,
                "sfx": req.music_data.get("sfx", []),
            },
            "segments": remotion_segments,
        }

        # ── Step 3: Direction QC ─────────────────────────
        direction_score = 8.0
        issues = []
        if not all(s.get("scene_overrides", {}).get("background_url") for s in remotion_segments):
            missing_bg = sum(1 for s in remotion_segments if not s.get("scene_overrides", {}).get("background_url"))
            if missing_bg > len(remotion_segments) * 0.3:
                direction_score -= 1.0
                issues.append(f"{missing_bg} segments missing background visuals")
        if total_duration_s < 10:
            direction_score -= 0.5
            issues.append("Very short total duration")

        direction_v3["direction_score"] = round(direction_score, 1)
        direction_v3["direction_issues"] = issues

        # ── Step 4: Store in DB ──────────────────────────
        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET v3_direction = $1, direction_score = $2, updated_at = NOW() "
                "WHERE content_id = $3",
                json.dumps(direction_v3), direction_score, req.content_id)
        except Exception as e:
            logger.warning("direction.db_update_failed", error=str(e))

        logger.info("direction.completed",
                     segments=len(remotion_segments),
                     duration=total_duration_s,
                     score=direction_score,
                     cost=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data={
                "direction_v3": direction_v3,
                "segment_count": len(remotion_segments),
                "total_duration_s": total_duration_s,
                "direction_score": round(direction_score, 1),
            },
            cost={"cost_usd": round(total_cost, 6), "provider": result.provider},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("direction.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.direction.main:app", host="0.0.0.0", port=8010, log_level="info")
