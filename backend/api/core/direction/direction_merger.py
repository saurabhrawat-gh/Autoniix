"""Direction Merger — Uses script v3 direction hints to reduce/eliminate LLM calls.

The script intelligence engine already generates a full Direction v3 config via
`direction_engine.py`. This module merges that with actual asset/voice data
and applies brand-aware enhancements, potentially skipping the GPT direction call.

LLM cost saving: ~$0.01-0.03 per video when script v3 hint is sufficient.
Intelligence cost: $0.00 — all computation is local.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from core.db import get_pool

logger = structlog.get_logger()

SECTION_PACING: dict[str, dict] = {
    "hook": {"min_duration_ms": 1500, "max_duration_ms": 5000, "preferred_camera": "zoom_in"},
    "intro": {"min_duration_ms": 3000, "max_duration_ms": 10000, "preferred_camera": "slow_pan"},
    "body": {"min_duration_ms": 5000, "max_duration_ms": 20000, "preferred_camera": "static"},
    "climax": {"min_duration_ms": 3000, "max_duration_ms": 15000, "preferred_camera": "slow_zoom"},
    "conclusion": {"min_duration_ms": 3000, "max_duration_ms": 10000, "preferred_camera": "pull_back"},
    "cta": {"min_duration_ms": 2000, "max_duration_ms": 8000, "preferred_camera": "static"},
}


def merge_script_direction_with_assets(script_v3_hint: dict,
                                        script_segments: list[dict],
                                        voice_manifest: dict,
                                        asset_manifest: list[dict],
                                        thumbnail_result: dict,
                                        music_data: dict,
                                        channel: dict) -> dict:
    """Merge script v3 direction with actual asset/voice data.
    
    Returns a complete Remotion v3 direction config that may not need LLM.
    """
    if not script_v3_hint or not script_v3_hint.get("segments"):
        return {}

    hint_segments = script_v3_hint.get("segments", [])
    hint_lookup = {s.get("id"): s for s in hint_segments}

    asset_lookup = {}
    for item in asset_manifest:
        seg_id = item.get("segment_id", "")
        asset_lookup[seg_id] = item

    segment_urls = voice_manifest.get("segment_urls", {})
    full_audio_url = voice_manifest.get("audio_url", "")

    is_long = channel.get("content_mode", "short") == "long_form"
    aspect = "16:9" if is_long else "9:16"
    resolution = {"width": 1920, "height": 1080} if is_long else {"width": 1080, "height": 1920}
    fps = 30
    brand_primary = channel.get("primary_color", "#1A237E")
    brand_accent = channel.get("accent_color", channel.get("secondary_color", "#FF6F00"))

    merged_segments = []
    cumulative_ms = 0

    for seg in script_segments:
        seg_id = seg.get("id", "s0")
        hint = hint_lookup.get(seg_id, {})
        duration_s = seg.get("duration_s", 10)
        duration_ms = int(duration_s * 1000)

        seg_asset = asset_lookup.get(seg_id, {})
        assets = seg_asset.get("assets", [])
        bg_url = assets[0]["url"] if assets else ""
        asset_type = seg_asset.get("type", "none")

        voice_url = segment_urls.get(seg_id, "")

        scene_preset = hint.get("scene_preset", "")
        if not scene_preset:
            if asset_type == "stock_video":
                scene_preset = "scene.stock_footage"
            elif asset_type == "generated_image":
                scene_preset = "scene.ken_burns"
            else:
                scene_preset = "scene.kinetic_typography"

        hint_camera = hint.get("camera", {})
        camera = {
            "type": hint_camera.get("type", "static"),
            "speed": hint_camera.get("speed", "medium"),
            "start_position": hint_camera.get("start_position", "center"),
            "end_position": hint_camera.get("end_position", ""),
        }

        hint_text = hint.get("text_strategy", {})
        text_overlay = seg.get("text_overlay", "")
        text_strategy = {
            "primary_text": hint_text.get("primary_text", text_overlay),
            "font_size": hint_text.get("font_size", "large"),
            "animation": hint_text.get("animation", "fade_in"),
            "position": hint_text.get("position", "center"),
            "timing_ms": hint_text.get("timing_ms", {"appear": 0, "duration": duration_ms}),
            "emphasis_words": hint_text.get("emphasis_words", seg.get("emphasis_words", [])),
        }

        hint_bg = hint.get("background_strategy", {})
        background_strategy = {
            "type": "asset" if bg_url else hint_bg.get("type", "gradient"),
            "primary_color": hint_bg.get("primary_color", brand_primary),
            "overlay_opacity": hint_bg.get("overlay_opacity", 0.0),
            "blur_amount": hint_bg.get("blur_amount", 0),
        }

        hint_motion = hint.get("motion_design", {})
        motion_design = {
            "elements": hint_motion.get("elements", []),
        }

        hint_audio = hint.get("audio_cues", {})
        audio_cues = {
            "sfx": hint_audio.get("sfx", []),
            "music_shift": hint_audio.get("music_shift", "none"),
        }

        hint_transition = hint.get("transition_in", {})
        transition_type = hint_transition.get("type", seg.get("transition", "cut"))

        merged_seg = {
            "id": seg_id,
            "start_ms": cumulative_ms,
            "duration_ms": duration_ms,
            "section": seg.get("section", "body"),
            "emotion": seg.get("emotion", ""),
            "scene_preset": scene_preset,
            "camera": camera,
            "scene_overrides": {
                "background_url": bg_url,
                "label": text_overlay,
                "animation": text_strategy["animation"],
                "text_position": text_strategy["position"],
                "emphasis_words": text_strategy["emphasis_words"],
            },
            "text_strategy": text_strategy,
            "background_strategy": background_strategy,
            "motion_design": motion_design,
            "audio_cues": audio_cues,
            "narration": {
                "text": seg.get("narration", ""),
                "word_count": len(seg.get("narration", "").split()),
                "audio_url": voice_url,
            },
            "transition_in": {
                "type": transition_type,
                "preset": f"trans.{transition_type}" if transition_type != "cut" else "trans.cut",
                "duration_ms": hint_transition.get("duration_ms", 500),
            },
            "visual_effects": hint.get("visual_effects", []),
        }
        merged_segments.append(merged_seg)
        cumulative_ms += duration_ms

    total_duration_s = cumulative_ms / 1000

    direction_v3 = {
        "version": "3.0",
        "meta": {
            "video_id": "",
            "channel_id": channel.get("channel_id", ""),
            "title": "",
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
                "heading": channel.get("font_heading", channel.get("font_family", "Inter")),
                "body": channel.get("font_body", channel.get("font_family", "Inter")),
            },
        },
        "grade_preset": channel.get("grade_preset", channel.get("color_grade_preset", "fx.grade.cinematic_teal_orange")),
        "global_overlays": [
            {"type": "vignette", "intensity": 0.3},
            {"type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15},
        ],
        "audio_master": {
            "narration_url": full_audio_url,
            "music_url": music_data.get("music", [{}])[0].get("url", "") if music_data.get("music") else "",
            "music_volume": 0.15,
            "ducking": True,
            "ducking_threshold": -20,
            "sfx": music_data.get("sfx", []),
        },
        "segments": merged_segments,
        "merged_from_script_v3": True,
    }

    return direction_v3


def score_merged_direction(direction_v3: dict) -> dict:
    """Score the quality of merged direction (same criteria as direction QC)."""
    segments = direction_v3.get("segments", [])
    if not segments:
        return {"score": 1.0, "issues": ["No segments"]}

    score = 10.0
    issues = []

    missing_bg = sum(1 for s in segments if not s.get("scene_overrides", {}).get("background_url"))
    if missing_bg > 0:
        penalty = min(2.0, missing_bg * 0.5)
        score -= penalty
        issues.append(f"{missing_bg} segments missing background")

    camera_types = set(s.get("camera", {}).get("type", "static") for s in segments)
    if len(camera_types) <= 1 and len(segments) > 2:
        score -= 1.0
        issues.append("No camera variety")

    presets = [s.get("scene_preset", "") for s in segments]
    consecutive = sum(1 for i in range(1, len(presets)) if presets[i] == presets[i-1])
    if consecutive > 0:
        score -= consecutive * 0.3
        issues.append(f"{consecutive} consecutive preset repeats")

    missing_text = sum(1 for s in segments if not s.get("text_strategy", {}).get("primary_text"))
    if missing_text > 0:
        score -= missing_text * 0.3

    score = max(1.0, round(score, 1))
    return {"score": score, "issues": issues}


async def store_direction_features(content_id: str, channel_id: str,
                                    direction_v3: dict, used_hint: bool,
                                    llm_tokens: int = 0) -> None:
    """Store direction features for learning."""
    segments = direction_v3.get("segments", [])
    try:
        pool = await get_pool()
        await pool.execute("""
            INSERT INTO direction_features (content_id, channel_id,
                segment_count, unique_scene_presets, unique_camera_types,
                avg_segment_duration_ms, has_motion_design, transition_variety,
                used_script_v3_hint, llm_tokens_used, direction_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            content_id, channel_id,
            len(segments),
            len(set(s.get("scene_preset", "") for s in segments)),
            len(set(s.get("camera", {}).get("type", "") for s in segments)),
            int(sum(s.get("duration_ms", 0) for s in segments) / max(len(segments), 1)),
            any(s.get("motion_design", {}).get("elements") for s in segments),
            len(set(s.get("transition_in", {}).get("type", "") for s in segments)),
            used_hint, llm_tokens,
            direction_v3.get("direction_score", 0),
        )
    except Exception as e:
        logger.warning("direction_merger.store_features_failed", error=str(e))
