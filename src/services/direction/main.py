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

import src.providers.boot  # noqa: F401
from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest

from src.services.direction.direction_merger import (
    merge_script_direction_with_assets,
    score_merged_direction,
    store_direction_features,
)
from src.observability.metrics import instrument_app

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

def _safe_format(template: str, **kwargs) -> str:
    """Replace {key} placeholders without failing on unknown/literal braces."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


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


instrument_app(app, service_name="direction")
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
        brand_primary = channel.get("primary_color", "#1A237E")
        brand_accent = channel.get("accent_color", "#FF6F00")

        # ── Intelligence: Try script v3 direction hint first ──
        use_hint_cfg = await _load_config("direction_use_script_v3_hint")
        use_hint = use_hint_cfg != "false"
        llm_enhance_cfg = await _load_config("direction_llm_enhance_enabled")
        llm_enhance = llm_enhance_cfg != "false"
        used_hint = False

        script_v3_hint = {}
        for seg in req.script_segments:
            if seg.get("direction_hint"):
                if not script_v3_hint:
                    script_v3_hint = {"segments": []}
                script_v3_hint["segments"].append(seg.get("direction_hint", {}))

        if use_hint and script_v3_hint.get("segments"):
            # Try to build direction from script v3 hints (cost: $0.00)
            merged = merge_script_direction_with_assets(
                script_v3_hint, req.script_segments,
                req.voice_manifest, req.asset_manifest,
                req.thumbnail_result, req.music_data, channel)

            if merged and merged.get("segments"):
                merged_qc = score_merged_direction(merged)
                merged_score = merged_qc.get("score", 0)

                if merged_score >= 7.0 and not llm_enhance:
                    # Merged direction is good enough, skip LLM entirely
                    merged["direction_score"] = merged_score
                    merged["direction_issues"] = merged_qc.get("issues", [])
                    merged["meta"]["video_id"] = req.content_id
                    merged["meta"]["title"] = req.title
                    used_hint = True

                    await store_direction_features(
                        req.content_id, req.channel_id, merged,
                        used_hint=True, llm_tokens=0)

                    try:
                        pool = await get_pool()
                        await pool.execute(
                            "UPDATE videos SET v3_direction = $1, direction_score = $2, updated_at = NOW() "
                            "WHERE content_id = $3",
                            json.dumps(merged), merged_score, req.content_id)
                    except Exception:
                        pass

                    logger.info("direction.completed_from_hint",
                                 segments=len(merged.get("segments", [])),
                                 score=merged_score, cost=0)

                    return ServiceResponse(
                        status="success",
                        data={
                            "direction_v3": merged,
                            "segment_count": len(merged.get("segments", [])),
                            "total_duration_s": merged.get("meta", {}).get("duration_target_seconds", 0),
                            "direction_score": round(merged_score, 1),
                            "intelligence": {"source": "script_v3_hint", "llm_cost": 0},
                        },
                        cost={"cost_usd": 0, "provider": "local"},
                    )

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

        system_prompt = _safe_format(prompt.get("system_prompt",
            "Generate per-segment visual direction for Remotion rendering. Respond in JSON."),
            aspect=aspect,
            resolution=json.dumps(resolution),
        )
        user_prompt = _safe_format(prompt.get("user_prompt_template",
            "Segments: {segments}\nChannel style: {visual_style}"),
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

            # Extract rich direction fields from GPT output
            gpt_camera = gpt_dir.get("camera", {})
            gpt_text_strategy = gpt_dir.get("text_strategy", {})
            gpt_bg_strategy = gpt_dir.get("background_strategy", {})
            gpt_motion = gpt_dir.get("motion_design", {})
            gpt_audio_cues = gpt_dir.get("audio_cues", {})
            gpt_transition = gpt_dir.get("transition_in", {})

            # Script-level emphasis_words and emotion
            script_emphasis = seg.get("emphasis_words", [])
            script_emotion = seg.get("emotion", "")

            remotion_seg = {
                "id": seg_id,
                "start_ms": cumulative_ms,
                "duration_ms": duration_ms,
                "section": seg.get("section", "body"),
                "emotion": script_emotion,
                "scene_preset": scene_preset,
                "camera": {
                    "type": gpt_camera.get("type", "static"),
                    "speed": gpt_camera.get("speed", "medium"),
                    "start_position": gpt_camera.get("start_position", "center"),
                    "end_position": gpt_camera.get("end_position", ""),
                },
                "scene_overrides": {
                    "background_url": bg_url,
                    "label": text_overlay,
                    "animation": gpt_dir.get("animation", gpt_text_strategy.get("animation", "fade_in")),
                    "zoom_direction": gpt_camera.get("type", "") if "zoom" in gpt_camera.get("type", "") else "",
                    "text_position": gpt_text_strategy.get("position", gpt_dir.get("text_position", "center")),
                    "emphasis_words": gpt_text_strategy.get("emphasis_words", gpt_dir.get("emphasis_words", script_emphasis)),
                },
                "text_strategy": {
                    "primary_text": gpt_text_strategy.get("primary_text", text_overlay),
                    "font_size": gpt_text_strategy.get("font_size", "large"),
                    "animation": gpt_text_strategy.get("animation", "fade_in"),
                    "position": gpt_text_strategy.get("position", "center"),
                    "timing_ms": gpt_text_strategy.get("timing_ms", {"appear": 0, "duration": duration_ms}),
                    "emphasis_words": gpt_text_strategy.get("emphasis_words", []),
                },
                "background_strategy": {
                    "type": gpt_bg_strategy.get("type", "asset" if bg_url else "gradient"),
                    "primary_color": gpt_bg_strategy.get("primary_color", brand_primary),
                    "overlay_opacity": gpt_bg_strategy.get("overlay_opacity", 0.0),
                    "blur_amount": gpt_bg_strategy.get("blur_amount", 0),
                },
                "motion_design": {
                    "elements": gpt_motion.get("elements", []),
                },
                "audio_cues": {
                    "sfx": gpt_audio_cues.get("sfx", []),
                    "music_shift": gpt_audio_cues.get("music_shift", "none"),
                },
                "narration": {
                    "text": narration,
                    "word_count": len(narration.split()),
                    "audio_url": voice_url,
                },
                "transition_in": {
                    "type": gpt_transition.get("type", f"{transition}" if transition != "cut" else "cut"),
                    "preset": f"trans.{gpt_transition.get('type', transition)}" if gpt_transition.get('type', transition) != "cut" else "trans.cut",
                    "duration_ms": gpt_transition.get("duration_ms", gpt_dir.get("transition_duration_ms", 500)),
                },
                "visual_effects": gpt_dir.get("visual_effects", []),
            }
            remotion_segments.append(remotion_seg)
            cumulative_ms += duration_ms

        total_duration_s = cumulative_ms / 1000

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

        # ── Step 3: Direction QC (enhanced) ───────────────
        direction_score = 10.0
        issues = []

        # Check backgrounds
        missing_bg = sum(1 for s in remotion_segments if not s.get("scene_overrides", {}).get("background_url"))
        if missing_bg > 0:
            penalty = min(2.0, missing_bg * 0.5)
            direction_score -= penalty
            issues.append(f"{missing_bg} segments missing background visuals")

        # Check text_strategy completeness
        missing_text = sum(1 for s in remotion_segments if not s.get("text_strategy", {}).get("primary_text"))
        if missing_text > 0:
            direction_score -= missing_text * 0.3
            issues.append(f"{missing_text} segments missing text_strategy")

        # Check emphasis_words
        missing_emphasis = sum(1 for s in remotion_segments
                               if not s.get("scene_overrides", {}).get("emphasis_words")
                               and not s.get("text_strategy", {}).get("emphasis_words"))
        if missing_emphasis > 0:
            direction_score -= missing_emphasis * 0.2
            issues.append(f"{missing_emphasis} segments missing emphasis_words")

        # Check camera movement (should not all be static)
        all_static = all(s.get("camera", {}).get("type", "static") == "static" for s in remotion_segments)
        if all_static and len(remotion_segments) > 2:
            direction_score -= 1.0
            issues.append("All segments use static camera — needs visual variety")

        # Check motion_design
        no_motion = sum(1 for s in remotion_segments if not s.get("motion_design", {}).get("elements"))
        if no_motion > len(remotion_segments) * 0.5:
            direction_score -= 0.5
            issues.append(f"{no_motion} segments have no motion_design elements")

        # Check consecutive scene_preset repetition
        presets = [s.get("scene_preset", "") for s in remotion_segments]
        consecutive_repeats = sum(1 for i in range(1, len(presets)) if presets[i] == presets[i-1])
        if consecutive_repeats > 0:
            direction_score -= consecutive_repeats * 0.3
            issues.append(f"{consecutive_repeats} consecutive scene_preset repeats")

        # Duration check
        if total_duration_s < 10:
            direction_score -= 0.5
            issues.append("Very short total duration")

        direction_score = max(1.0, round(direction_score, 1))

        direction_v3["direction_score"] = round(direction_score, 1)
        direction_v3["direction_issues"] = issues

        # Intelligence: Store direction features for learning
        await store_direction_features(
            req.content_id, req.channel_id, direction_v3,
            used_hint=False, llm_tokens=result.tokens_in + result.tokens_out)

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
                "intelligence": {"source": "llm", "llm_cost": round(total_cost, 6)},
            },
            cost={"cost_usd": round(total_cost, 6), "provider": result.provider},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("direction.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


async def _load_config(key: str) -> str:
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = $1", key)
        return row["config_value"] if row else ""
    except Exception:
        return ""


if __name__ == "__main__":
    uvicorn.run("src.services.direction.main:app", host="0.0.0.0", port=8010, log_level="info")
