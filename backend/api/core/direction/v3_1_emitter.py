"""Direction v3.1 Timeline Emitter — Sub-second granularity.

This module emits Direction v3.1 timelines with:
- Timeline keyframes every ≤500ms
- Word-level captions from voice alignment
- Micro-beats (≤100ms precision)
- Audio ducking envelope

Tier 3 upgrade: Voice service now provides measured duration + word alignment,
so Direction can emit frame-accurate timelines instead of estimates.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def emit_timeline_keyframes(
    voice_manifest: dict,
    duration_ms: int,
    max_gap_ms: int = 500,
) -> list[dict]:
    """
    Emit timeline keyframes at ≤500ms spacing.

    Args:
        voice_manifest: Output from voice service with emphasis_hits
        duration_ms: Total video duration in milliseconds
        max_gap_ms: Maximum gap between keyframes (default 500ms)

    Returns:
        List of keyframe dicts with at_ms, camera, ease
    """
    keyframes = []

    # Start keyframe
    keyframes.append(
        {
            "at_ms": 0,
            "camera": {"position": {"x": 0, "y": 0, "z": 5}, "scale": 1.0, "rotation": 0},
            "ease": "easeInOutCubic",
        }
    )

    # Add keyframes at emphasis hits (hero moments)
    for hit in voice_manifest.get("emphasis_hits", []):
        keyframes.append(
            {
                "at_ms": hit["at_ms"],
                "camera": {
                    "position": {"x": 0, "y": 0, "z": 4.5},
                    "scale": 1.1,  # Slight zoom on emphasis
                    "rotation": 0,
                },
                "ease": "easeOutQuad",
            }
        )

    # Sort by time
    keyframes.sort(key=lambda k: k["at_ms"])

    # Fill gaps > max_gap_ms with interpolated keyframes
    filled = [keyframes[0]]

    for i in range(1, len(keyframes)):
        prev = filled[-1]
        curr = keyframes[i]
        gap = curr["at_ms"] - prev["at_ms"]

        if gap > max_gap_ms:
            # Insert interpolated keyframes
            num_fills = gap // max_gap_ms
            for j in range(1, num_fills + 1):
                t = j / (num_fills + 1)
                filled.append(
                    {
                        "at_ms": prev["at_ms"] + (j * max_gap_ms),
                        "camera": _interpolate_camera(prev["camera"], curr["camera"], t),
                        "ease": "linear",
                    }
                )

        filled.append(curr)

    # Add end keyframe if needed
    if filled[-1]["at_ms"] < duration_ms - max_gap_ms:
        filled.append(
            {
                "at_ms": duration_ms,
                "camera": {"position": {"x": 0, "y": 0, "z": 5}, "scale": 1.0, "rotation": 0},
                "ease": "easeInOutCubic",
            }
        )

    logger.info("direction.timeline_emitted", keyframes=len(filled), max_gap_ms=max_gap_ms)

    return filled


def _interpolate_camera(cam_a: dict, cam_b: dict, t: float) -> dict:
    """Linearly interpolate between two camera states."""
    pos_a = cam_a.get("position", {"x": 0, "y": 0, "z": 5})
    pos_b = cam_b.get("position", {"x": 0, "y": 0, "z": 5})

    return {
        "position": {
            "x": pos_a["x"] + (pos_b["x"] - pos_a["x"]) * t,
            "y": pos_a["y"] + (pos_b["y"] - pos_a["y"]) * t,
            "z": pos_a["z"] + (pos_b["z"] - pos_a["z"]) * t,
        },
        "scale": cam_a.get("scale", 1.0) + (cam_b.get("scale", 1.0) - cam_a.get("scale", 1.0)) * t,
        "rotation": cam_a.get("rotation", 0) + (cam_b.get("rotation", 0) - cam_a.get("rotation", 0)) * t,
    }


def emit_captions(voice_manifest: dict) -> list[dict]:
    """
    Emit word-level captions from voice word alignment.

    Args:
        voice_manifest: Output from voice service with word_alignment

    Returns:
        List of caption dicts with word, start_ms, end_ms, style, chars
    """
    captions = []

    for word_data in voice_manifest.get("word_alignment", []):
        # Extract character-level timing for reveal animations
        chars = _get_character_timing(word_data)

        captions.append(
            {
                "word": word_data["word"],
                "start_ms": word_data["start_ms"],
                "end_ms": word_data["end_ms"],
                "style": "emphasis" if word_data.get("is_emphasis") else "normal",
                "chars": chars,
                "segment_id": word_data.get("segment_id"),
            }
        )

    logger.info("direction.captions_emitted", words=len(captions))

    return captions


def _get_character_timing(word: dict) -> list[dict]:
    """
    Break word into characters with timing for reveal animations.

    Returns:
        [{"char": "b", "at_ms": 1000}, {"char": "r", "at_ms": 1050}, ...]
    """
    text = word["word"]
    start_ms = word["start_ms"]
    end_ms = word["end_ms"]

    chars = list(text)
    if not chars:
        return []

    duration_ms = end_ms - start_ms
    char_duration = duration_ms / len(chars)

    result = []
    current_time = start_ms

    for char in chars:
        result.append({"char": char, "at_ms": int(current_time)})
        current_time += char_duration

    return result


def emit_micro_beats(
    voice_emphasis_hits: list[dict],
    music_beat_map_ms: list[int] | None = None,
) -> list[dict]:
    """
    Emit micro-beats (≤100ms precision) for visual effects.

    Args:
        voice_emphasis_hits: Emphasis hits from voice service
        music_beat_map_ms: Optional music beat map for sync

    Returns:
        List of micro-beat dicts with at_ms, intensity, type
    """
    micro_beats = []

    for hit in voice_emphasis_hits:
        # Determine effect type based on intensity
        intensity = hit.get("intensity", 0.5)

        if intensity >= 0.9:
            effect_type = "zoom_punch"
        elif intensity >= 0.7:
            effect_type = "flash"
        else:
            effect_type = "subtle_glow"

        micro_beats.append(
            {
                "at_ms": hit["at_ms"],
                "intensity": intensity,
                "type": effect_type,
                "word": hit.get("word", ""),
            }
        )

    # Add music beat sync if available
    if music_beat_map_ms:
        for beat_ms in music_beat_map_ms:
            # Check if this beat aligns with a voice hit
            aligned = any(abs(beat_ms - hit["at_ms"]) <= 100 for hit in voice_emphasis_hits)

            if not aligned:
                # Add subtle beat marker
                micro_beats.append(
                    {
                        "at_ms": beat_ms,
                        "intensity": 0.5,
                        "type": "beat_marker",
                        "word": "",
                    }
                )

    # Sort by time
    micro_beats.sort(key=lambda b: b["at_ms"])

    logger.info("direction.micro_beats_emitted", beats=len(micro_beats))

    return micro_beats


def emit_ducking_envelope(
    voice_manifest: dict,
    total_duration_ms: int,
) -> list[dict]:
    """
    Emit audio ducking envelope (music volume reduction during voice).

    Args:
        voice_manifest: Output from voice service
        total_duration_ms: Total video duration

    Returns:
        List of ducking points with at_ms, music_volume_db
    """
    envelope = []

    # Start with full music volume
    envelope.append({"at_ms": 0, "music_volume_db": 0})

    # Get voice timing from word alignment or fallback to duration
    word_alignment = voice_manifest.get("word_alignment", [])

    if word_alignment:
        # Use word alignment for precise ducking
        first_word_ms = word_alignment[0]["start_ms"]
        last_word_ms = word_alignment[-1]["end_ms"]

        # Fade down before first word
        envelope.append({"at_ms": max(0, first_word_ms - 200), "music_volume_db": 0})
        envelope.append({"at_ms": first_word_ms, "music_volume_db": -12})

        # Keep ducked during voice
        envelope.append({"at_ms": last_word_ms, "music_volume_db": -12})

        # Fade up after last word
        envelope.append({"at_ms": min(total_duration_ms, last_word_ms + 200), "music_volume_db": 0})
    else:
        # Fallback: duck for entire duration estimate
        duration_ms = voice_manifest.get("duration_ms", 0)
        if duration_ms > 0:
            envelope.append({"at_ms": 0, "music_volume_db": -12})
            envelope.append({"at_ms": duration_ms, "music_volume_db": -12})
            envelope.append({"at_ms": min(total_duration_ms, duration_ms + 200), "music_volume_db": 0})

    # End with full music volume
    if envelope[-1]["at_ms"] < total_duration_ms:
        envelope.append({"at_ms": total_duration_ms, "music_volume_db": 0})

    logger.info("direction.ducking_envelope_emitted", points=len(envelope))

    return envelope


def validate_timeline_density(timeline: list[dict], max_gap_ms: int = 500) -> dict:
    """
    Validate timeline has keyframes every ≤max_gap_ms.

    Returns:
        {
            "is_valid": bool,
            "max_gap_ms": int,
            "gaps": [{"start_ms": int, "end_ms": int, "gap_ms": int}, ...]
        }
    """
    if not timeline:
        return {"is_valid": False, "max_gap_ms": 0, "gaps": []}

    gaps = []
    max_gap = 0

    for i in range(1, len(timeline)):
        gap_ms = timeline[i]["at_ms"] - timeline[i - 1]["at_ms"]
        max_gap = max(max_gap, gap_ms)

        if gap_ms > max_gap_ms:
            gaps.append(
                {
                    "start_ms": timeline[i - 1]["at_ms"],
                    "end_ms": timeline[i]["at_ms"],
                    "gap_ms": gap_ms,
                }
            )

    is_valid = len(gaps) == 0

    return {
        "is_valid": is_valid,
        "max_gap_ms": max_gap,
        "gaps": gaps,
    }
