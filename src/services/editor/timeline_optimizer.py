"""Timeline Optimizer — Analyzes and adjusts segment pacing for maximum retention.

Takes the direction v3 config and optimizes:
- Segment durations (too long = boring, too short = confusing)
- Transition placement and timing
- Beat synchronization with narration pace
- Hook pacing (first 3 seconds critical)
- CTA placement optimization

Intelligence cost: $0.00 — all computation is local.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

# Optimal pacing rules
PACING_RULES: dict[str, dict] = {
    "hook": {"min_ms": 1500, "max_ms": 5000, "ideal_ms": 3000, "tolerance_pct": 0.30},
    "intro": {"min_ms": 2000, "max_ms": 8000, "ideal_ms": 5000, "tolerance_pct": 0.25},
    "body": {"min_ms": 4000, "max_ms": 20000, "ideal_ms": 10000, "tolerance_pct": 0.20},
    "climax": {"min_ms": 3000, "max_ms": 12000, "ideal_ms": 8000, "tolerance_pct": 0.25},
    "conclusion": {"min_ms": 2000, "max_ms": 8000, "ideal_ms": 5000, "tolerance_pct": 0.25},
    "cta": {"min_ms": 1500, "max_ms": 6000, "ideal_ms": 3000, "tolerance_pct": 0.30},
}

# Transition rules
TRANSITION_AFFINITY: dict[str, list[str]] = {
    "hook": ["cut", "impact_zoom", "flash"],
    "body": ["dissolve", "slide", "push", "wipe"],
    "climax": ["zoom_in", "flash", "ripple"],
    "conclusion": ["dissolve", "fade"],
    "cta": ["slide_up", "bounce"],
}


def analyze_pacing(direction_v3: dict) -> dict:
    """Analyze pacing of the video and suggest adjustments."""
    segments = direction_v3.get("segments", [])
    if not segments:
        return {"pacing_score": 0, "adjustments": []}

    adjustments = []
    total_duration_ms = 0
    section_durations: dict[str, list[int]] = {}

    for seg in segments:
        duration_ms = seg.get("duration_ms", 10000)
        section = seg.get("section", "body")
        total_duration_ms += duration_ms

        if section not in section_durations:
            section_durations[section] = []
        section_durations[section].append(duration_ms)

        rules = PACING_RULES.get(section, PACING_RULES["body"])

        # Check if segment is too long
        if duration_ms > rules["max_ms"]:
            ideal = rules["ideal_ms"]
            adjustments.append({
                "segment_id": seg.get("id"),
                "type": "duration_reduce",
                "current_ms": duration_ms,
                "suggested_ms": ideal,
                "reason": f"Segment too long for {section} ({duration_ms}ms > {rules['max_ms']}ms)",
                "priority": "high",
            })

        # Check if segment is too short
        elif duration_ms < rules["min_ms"]:
            adjustments.append({
                "segment_id": seg.get("id"),
                "type": "duration_extend",
                "current_ms": duration_ms,
                "suggested_ms": rules["min_ms"],
                "reason": f"Segment too short for {section} ({duration_ms}ms < {rules['min_ms']}ms)",
                "priority": "medium",
            })

    # Check overall pace variation (should vary, not be monotone)
    durations = [s.get("duration_ms", 10000) for s in segments]
    if len(durations) > 2:
        duration_cv = np.std(durations) / np.mean(durations) if np.mean(durations) > 0 else 0
        if duration_cv < 0.15:
            adjustments.append({
                "segment_id": "global",
                "type": "pace_monotone",
                "reason": f"Low pace variation (CV={duration_cv:.2f}). Vary segment durations more.",
                "priority": "medium",
            })

    # Score pacing
    pacing_score = 10.0
    for adj in adjustments:
        if adj["priority"] == "high":
            pacing_score -= 1.0
        elif adj["priority"] == "medium":
            pacing_score -= 0.5

    pacing_score = max(1.0, round(pacing_score, 1))

    return {
        "pacing_score": pacing_score,
        "adjustments": adjustments,
        "total_duration_ms": total_duration_ms,
        "segment_count": len(segments),
    }


def optimize_transitions(direction_v3: dict) -> dict:
    """Optimize transitions between segments for visual flow."""
    segments = direction_v3.get("segments", [])
    if not segments:
        return {"changes": [], "transition_score": 0}

    changes = []
    transitions_used = []

    for i, seg in enumerate(segments):
        section = seg.get("section", "body")
        current_trans = seg.get("transition_in", {}).get("type", "cut")
        transitions_used.append(current_trans)

        # Check transition is appropriate for section
        good_transitions = TRANSITION_AFFINITY.get(section, TRANSITION_AFFINITY["body"])
        if current_trans not in good_transitions and current_trans != "cut":
            suggested = good_transitions[0]
            changes.append({
                "segment_id": seg.get("id"),
                "type": "transition_change",
                "from": current_trans,
                "to": suggested,
                "reason": f"'{current_trans}' not ideal for {section} section",
            })

        # Check consecutive duplicate transitions
        if i > 0 and current_trans == transitions_used[i-1] and current_trans != "cut":
            alts = [t for t in good_transitions if t != current_trans]
            if alts:
                changes.append({
                    "segment_id": seg.get("id"),
                    "type": "transition_variety",
                    "from": current_trans,
                    "to": alts[0],
                    "reason": "Consecutive same transitions — vary for visual interest",
                })

    # Transition variety score
    unique_transitions = len(set(transitions_used))
    variety_score = min(10.0, unique_transitions * 2.5)

    return {
        "changes": changes,
        "transition_score": round(variety_score, 1),
        "unique_transitions": unique_transitions,
        "total_transitions": len(transitions_used),
    }


def apply_pacing_adjustments(direction_v3: dict, adjustments: list[dict],
                              apply_high_only: bool = False) -> dict:
    """Apply pacing adjustments to direction v3 config."""
    segments = direction_v3.get("segments", [])
    seg_lookup = {s.get("id"): s for s in segments}
    applied = 0

    for adj in adjustments:
        if apply_high_only and adj.get("priority") != "high":
            continue

        seg_id = adj.get("segment_id")
        if seg_id == "global":
            continue

        seg = seg_lookup.get(seg_id)
        if not seg:
            continue

        if adj["type"] in ("duration_reduce", "duration_extend"):
            seg["duration_ms"] = adj["suggested_ms"]
            applied += 1

    # Recalculate start_ms
    cumulative = 0
    for seg in segments:
        seg["start_ms"] = cumulative
        cumulative += seg.get("duration_ms", 10000)

    direction_v3["meta"]["duration_target_seconds"] = cumulative / 1000
    return {"applied": applied, "direction_v3": direction_v3}


def apply_transition_changes(direction_v3: dict, changes: list[dict]) -> dict:
    """Apply transition changes to direction v3 config."""
    segments = direction_v3.get("segments", [])
    seg_lookup = {s.get("id"): s for s in segments}
    applied = 0

    for change in changes:
        seg = seg_lookup.get(change.get("segment_id"))
        if not seg:
            continue
        seg["transition_in"]["type"] = change["to"]
        seg["transition_in"]["preset"] = f"trans.{change['to']}"
        applied += 1

    return {"applied": applied}
