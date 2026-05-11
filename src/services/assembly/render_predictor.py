"""Render Success Predictor — Predicts render success probability.

Uses direction complexity analysis to:
- Predict if a render will succeed before submitting
- Estimate render duration
- Identify potential failure points
- Smart retry with simplified direction on failure

Intelligence cost: $0.00 — heuristic analysis, all local.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from src.db import get_pool

logger = structlog.get_logger()


def compute_direction_complexity(direction_v3: dict) -> dict:
    """Compute complexity score for a direction v3 config.
    
    Higher complexity = higher render time and failure risk.
    """
    segments = direction_v3.get("segments", [])
    if not segments:
        return {"complexity": 0, "risk": "low"}

    score = 0.0
    risk_factors = []

    # Segment count impact
    seg_count = len(segments)
    score += seg_count * 0.3
    if seg_count > 15:
        risk_factors.append(f"High segment count: {seg_count}")

    # Motion design complexity
    motion_count = sum(
        len(s.get("motion_design", {}).get("elements", []))
        for s in segments
    )
    score += motion_count * 0.5
    if motion_count > 20:
        risk_factors.append(f"Many motion elements: {motion_count}")

    # Visual effects
    vfx_count = sum(len(s.get("visual_effects", [])) for s in segments)
    score += vfx_count * 0.3

    # Unique scene presets (more variety = more template switches)
    unique_presets = len(set(s.get("scene_preset", "") for s in segments))
    score += unique_presets * 0.2

    # Total duration
    total_ms = sum(s.get("duration_ms", 0) for s in segments)
    duration_min = total_ms / 60000
    score += duration_min * 0.5
    if duration_min > 10:
        risk_factors.append(f"Long video: {duration_min:.1f} minutes")

    # SFX count
    sfx_count = sum(
        len(s.get("audio_cues", {}).get("sfx", []))
        for s in segments
    )
    score += sfx_count * 0.2

    # Global overlays
    overlays = len(direction_v3.get("global_overlays", []))
    score += overlays * 0.3

    complexity = round(score, 2)
    risk = "high" if complexity > 8 else "medium" if complexity > 4 else "low"

    return {
        "complexity": complexity,
        "risk": risk,
        "risk_factors": risk_factors,
        "segment_count": seg_count,
        "total_duration_min": round(duration_min, 1),
        "motion_elements": motion_count,
        "vfx_count": vfx_count,
    }


def estimate_render_duration(complexity: dict) -> float:
    """Estimate render duration in seconds based on complexity."""
    base = 30  # Minimum 30 seconds
    per_segment = 10  # ~10s per segment
    per_minute_video = 20  # 20s per minute of video

    # Use per-field detail when available; fall back to top-level complexity score.
    complexity_score = complexity.get("complexity", 0)
    estimate = (
        base +
        complexity.get("segment_count", 0) * per_segment +
        complexity.get("total_duration_min", 0) * per_minute_video +
        complexity.get("motion_elements", 0) * 3 +
        complexity.get("vfx_count", 0) * 5 +
        complexity_score * 2  # raw score contribution when detail keys are absent
    )

    risk_factor = {"high": 1.5, "medium": 1.2, "low": 1.0}.get(
        complexity.get("risk", "low"), 1.0
    )
    return round(estimate * risk_factor, 0)


def simplify_direction_for_retry(direction_v3: dict) -> dict:
    """Simplify direction v3 for retry after render failure.
    
    Removes complex elements that might cause rendering issues.
    """
    simplified = json.loads(json.dumps(direction_v3))  # Deep copy
    segments = simplified.get("segments", [])

    for seg in segments:
        # Simplify motion design
        seg["motion_design"] = {"elements": []}
        # Remove visual effects
        seg["visual_effects"] = []
        # Simplify transitions to cuts
        seg["transition_in"] = {"type": "cut", "preset": "trans.cut", "duration_ms": 0}
        # Simplify camera to static
        seg["camera"] = {"type": "static", "speed": "medium",
                         "start_position": "center", "end_position": ""}

    # Remove complex overlays
    simplified["global_overlays"] = [
        o for o in simplified.get("global_overlays", [])
        if o.get("type") in ("vignette",)
    ]

    simplified["simplified_for_retry"] = True
    return simplified


async def log_render_attempt(content_id: str, channel_id: str, render_id: str,
                              complexity: dict, success: bool,
                              render_duration_s: float = 0,
                              video_duration_s: float = 0,
                              retry_count: int = 0,
                              error_category: str = "") -> None:
    """Log render attempt for ML learning."""
    try:
        pool = await get_pool()
        await pool.execute("""
            INSERT INTO assembly_render_log (content_id, channel_id, render_id,
                segment_count, direction_complexity,
                render_success, render_duration_s, video_duration_s,
                retry_count, error_category, production_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            content_id, channel_id, render_id,
            complexity.get("segment_count", 0),
            complexity.get("complexity", 0),
            success, render_duration_s, video_duration_s,
            retry_count, error_category, 0.0,
        )
    except Exception as e:
        logger.warning("render_predictor.log_failed", error=str(e))
