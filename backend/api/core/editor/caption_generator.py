"""Caption Generator — Generates word-level caption data for Remotion.

Creates per-word timing aligned with narration audio for:
- Word highlight captions (karaoke style)
- Subtitle generation
- Emphasis word animation triggers

Uses WPM estimation from narration text + audio duration.
Intelligence cost: $0.00 — all computation is local.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()

CAPTION_STYLES: dict[str, dict] = {
    "word_highlight": {
        "animation": "highlight",
        "bg_color": "rgba(0,0,0,0.7)",
        "text_color": "#FFFFFF",
        "highlight_color": "#FFD700",
        "font_size": 36,
        "position": "bottom_center",
        "max_words_per_line": 6,
    },
    "word_underline": {
        "animation": "underline",
        "bg_color": "transparent",
        "text_color": "#FFFFFF",
        "highlight_color": "#FF6F00",
        "font_size": 32,
        "position": "bottom_center",
        "max_words_per_line": 8,
    },
    "typewriter": {
        "animation": "typewriter",
        "bg_color": "rgba(0,0,0,0.8)",
        "text_color": "#00FF00",
        "highlight_color": "#00FF00",
        "font_size": 28,
        "position": "center",
        "max_words_per_line": 5,
    },
    "minimal": {
        "animation": "fade",
        "bg_color": "transparent",
        "text_color": "#FFFFFF",
        "highlight_color": "#FFFFFF",
        "font_size": 28,
        "position": "bottom_center",
        "max_words_per_line": 10,
    },
}


def generate_captions(direction_v3: dict, caption_style: str = "word_highlight") -> dict:
    """Generate word-level caption data for all segments.

    Returns caption config compatible with Remotion rendering.
    """
    segments = direction_v3.get("segments", [])
    style = CAPTION_STYLES.get(caption_style, CAPTION_STYLES["word_highlight"])

    caption_segments = []
    total_words = 0

    for seg in segments:
        narration = seg.get("narration", {})
        text = narration.get("text", "") if isinstance(narration, dict) else ""
        if not text:
            continue

        start_ms = seg.get("start_ms", 0)
        duration_ms = seg.get("duration_ms", 10000)
        emphasis_words = seg.get("scene_overrides", {}).get("emphasis_words", [])
        if not emphasis_words:
            emphasis_words = seg.get("text_strategy", {}).get("emphasis_words", [])

        words = text.split()
        if not words:
            continue

        word_duration_ms = duration_ms / len(words)
        word_timings = []
        current_ms = start_ms

        for word in words:
            clean_word = re.sub(r"[^\w\'-]", "", word)
            is_emphasis = clean_word.lower() in [w.lower() for w in emphasis_words]

            this_duration = word_duration_ms * 1.3 if is_emphasis else word_duration_ms

            word_timings.append(
                {
                    "word": word,
                    "start_ms": round(current_ms),
                    "end_ms": round(current_ms + this_duration),
                    "is_emphasis": is_emphasis,
                }
            )
            current_ms += word_duration_ms
            total_words += 1

        lines = []
        max_per_line = style.get("max_words_per_line", 6)
        for i in range(0, len(word_timings), max_per_line):
            line_words = word_timings[i : i + max_per_line]
            lines.append(
                {
                    "words": line_words,
                    "text": " ".join(w["word"] for w in line_words),
                    "start_ms": line_words[0]["start_ms"],
                    "end_ms": line_words[-1]["end_ms"],
                }
            )

        caption_segments.append(
            {
                "segment_id": seg.get("id"),
                "lines": lines,
                "word_count": len(words),
            }
        )

    return {
        "caption_style": caption_style,
        "style_config": style,
        "segments": caption_segments,
        "total_words": total_words,
        "total_lines": sum(len(cs["lines"]) for cs in caption_segments),
    }


def generate_audio_mix_config(direction_v3: dict, duck_db: float = -12) -> dict:
    """Generate audio mixing configuration for Remotion.

    Handles narration/music volume balancing and SFX placement.
    """
    segments = direction_v3.get("segments", [])
    audio_master = direction_v3.get("audio_master", {})

    duck_regions = []
    for seg in segments:
        narration = seg.get("narration", {})
        has_narration = bool(narration.get("text")) if isinstance(narration, dict) else False
        if has_narration:
            duck_regions.append(
                {
                    "start_ms": seg.get("start_ms", 0),
                    "end_ms": seg.get("start_ms", 0) + seg.get("duration_ms", 0),
                    "duck_db": duck_db,
                    "transition_ms": 200,
                }
            )

    sfx_placements = []
    for seg in segments:
        audio_cues = seg.get("audio_cues", {})
        sfx_list = audio_cues.get("sfx", [])
        for sfx in sfx_list:
            sfx_name = sfx if isinstance(sfx, str) else sfx.get("name", "")
            sfx_placements.append(
                {
                    "segment_id": seg.get("id"),
                    "start_ms": seg.get("start_ms", 0),
                    "sfx_name": sfx_name,
                    "volume_db": -6,
                }
            )

    return {
        "narration_volume_db": 0,
        "music_volume_db": -15,
        "duck_regions": duck_regions,
        "sfx_placements": sfx_placements,
        "master_settings": {
            "narration_url": audio_master.get("narration_url", ""),
            "music_url": audio_master.get("music_url", ""),
            "normalize": True,
            "limiter_threshold_db": -1,
        },
    }
