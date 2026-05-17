"""Final QC Brain — Comprehensive pre-render quality check.

Runs all quality checks on the assembled direction v3 before sending to
Remotion for rendering. Catches issues that would cause render failures
or low-quality output.

Intelligence cost: $0.00 — all heuristic computation.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def run_final_qc(direction_v3: dict, captions: dict = None,
                  audio_mix: dict = None) -> dict:
    """Run comprehensive QC on the final direction v3 config.
    
    Returns {score: float, passed: bool, issues: list, warnings: list}.
    """
    score = 10.0
    issues = []     # Hard failures
    warnings = []   # Soft warnings

    segments = direction_v3.get("segments", [])
    meta = direction_v3.get("meta", {})

    if not segments:
        return {"score": 0, "passed": False, "issues": ["No segments in direction"]}

    # 1. Timeline Integrity
    for i, seg in enumerate(segments):
        if i == 0:
            if seg.get("start_ms", -1) != 0:
                issues.append(f"First segment start_ms should be 0, got {seg.get('start_ms')}")
                score -= 1.0
        else:
            prev = segments[i-1]
            expected = prev.get("start_ms", 0) + prev.get("duration_ms", 0)
            actual = seg.get("start_ms", 0)
            if actual != expected:
                issues.append(f"Timeline gap at segment {seg.get('id')}: expected {expected}ms, got {actual}ms")
                score -= 1.0

    # 2. Duration Sanity
    total_ms = sum(s.get("duration_ms", 0) for s in segments)
    target_s = meta.get("duration_target_seconds", 0)
    if target_s and abs(total_ms / 1000 - target_s) > target_s * 0.2:
        issues.append(f"Duration mismatch: segments={total_ms/1000:.1f}s, target={target_s:.1f}s")
        score -= 0.5

    if total_ms < 5000:
        warnings.append("Very short video (< 5 seconds)")
    if total_ms > 1800000:
        warnings.append("Very long video (> 30 minutes)")

    # 3. Narration-Audio Alignment
    for seg in segments:
        narration = seg.get("narration", {})
        if isinstance(narration, dict):
            has_text = bool(narration.get("text"))
            has_audio = bool(narration.get("audio_url"))
            if has_text and not has_audio:
                warnings.append(f"Segment {seg.get('id')}: narration text but no audio_url")
                score -= 0.5

    # 4. Background Coverage
    missing_bg = 0
    for seg in segments:
        bg_url = seg.get("scene_overrides", {}).get("background_url", "")
        bg_type = seg.get("background_strategy", {}).get("type", "")
        if not bg_url and bg_type not in ("gradient", "solid"):
            missing_bg += 1
    if missing_bg > 0:
        warnings.append(f"{missing_bg} segments missing background (no asset, no fallback)")
        score -= min(2.0, missing_bg * 0.3)

    # 5. Camera Variety
    camera_types = [s.get("camera", {}).get("type", "static") for s in segments]
    unique_cameras = len(set(camera_types))
    if unique_cameras <= 1 and len(segments) > 3:
        warnings.append("All segments use same camera type — needs visual variety")
        score -= 0.5

    # 6. Transition Variety
    transitions = [s.get("transition_in", {}).get("type", "cut") for s in segments]
    unique_trans = len(set(transitions))
    consecutive_same = sum(1 for i in range(1, len(transitions)) if transitions[i] == transitions[i-1])
    if consecutive_same > 2:
        warnings.append(f"{consecutive_same} consecutive same transitions")
        score -= 0.3

    # 7. Audio Master
    audio_master = direction_v3.get("audio_master", {})
    if not audio_master.get("narration_url"):
        issues.append("No master narration_url")
        score -= 1.0

    # 8. Theme Completeness
    theme = direction_v3.get("theme", {})
    if not theme.get("primary_color"):
        warnings.append("No primary_color in theme")
        score -= 0.2
    if not theme.get("fonts", {}).get("heading"):
        warnings.append("No heading font specified")
        score -= 0.2

    # 9. Emphasis Words Coverage
    missing_emphasis = sum(
        1 for s in segments
        if not s.get("scene_overrides", {}).get("emphasis_words")
        and not s.get("text_strategy", {}).get("emphasis_words")
    )
    if missing_emphasis > len(segments) * 0.5:
        warnings.append(f"{missing_emphasis}/{len(segments)} segments missing emphasis_words")
        score -= 0.3

    # 10. Caption Validation
    if captions:
        caption_words = captions.get("total_words", 0)
        narration_words = sum(
            s.get("narration", {}).get("word_count", 0)
            if isinstance(s.get("narration"), dict)
            else len(str(s.get("narration", "")).split())
            for s in segments
        )
        if narration_words > 0 and caption_words == 0:
            warnings.append("Narration present but no captions generated")
            score -= 0.3

    score = max(1.0, round(score, 1))
    passed = score >= 7.0 and len(issues) == 0

    return {
        "score": score,
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "segment_count": len(segments),
            "total_duration_ms": total_ms,
            "unique_cameras": unique_cameras,
            "unique_transitions": unique_trans,
            "missing_backgrounds": missing_bg,
        },
    }
