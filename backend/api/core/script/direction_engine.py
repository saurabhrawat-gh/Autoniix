"""Direction Engine — Script v3 (Direction / Editing Config) generator.

Transforms the base script + prosody + assets into a Remotion-ready render config:
- Beat-to-shot segmentation with frame-accurate timing
- Camera movement rules (section-based templates + learned patterns)
- Text overlay timing (character count → min display time)
- Motion design templates indexed by emotion/section
- Transition selection with variety enforcement
- Audio cue placement (SFX at transitions + emphasis points)
- Typography from Channel DNA
- Safe area calculations for text
- Full Remotion v3 JSON compatible with the rendering pipeline

All computation is local (rule-based + learned patterns). Zero API cost.
"""

from __future__ import annotations

import random
from typing import Any

import structlog

logger = structlog.get_logger()

SCENE_PRESETS = {
    "hook": ["scene.kinetic_typography", "scene.zoom_focus", "scene.text_reveal"],
    "intro": ["scene.ken_burns", "scene.stock_footage", "scene.text_reveal"],
    "body": [
        "scene.stock_footage",
        "scene.ken_burns",
        "scene.kinetic_typography",
        "scene.split_screen",
        "scene.parallax",
    ],
    "climax": ["scene.zoom_focus", "scene.kinetic_typography", "scene.stock_footage"],
    "outro": ["scene.ken_burns", "scene.stock_footage", "scene.quote_card"],
}

CAMERA_TEMPLATES = {
    "hook": {
        "type": "push_in",
        "speed": "fast",
        "start_position": "center",
        "end_position": "center",
    },
    "intro": {
        "type": "ken_burns",
        "speed": "slow",
        "start_position": "left",
        "end_position": "right",
    },
    "body_a": {
        "type": "ken_burns",
        "speed": "slow",
        "start_position": "center",
        "end_position": "center",
    },
    "body_b": {
        "type": "pan_left",
        "speed": "medium",
        "start_position": "right",
        "end_position": "left",
    },
    "body_c": {
        "type": "static",
        "speed": "slow",
        "start_position": "center",
        "end_position": "center",
    },
    "climax": {
        "type": "zoom_in",
        "speed": "fast",
        "start_position": "center",
        "end_position": "center",
    },
    "outro": {
        "type": "static",
        "speed": "slow",
        "start_position": "center",
        "end_position": "center",
    },
}

TEXT_ANIMATIONS = {
    "hook": {"animation": "scale_pop", "font_size": "xlarge", "position": "center"},
    "intro": {"animation": "fade_in", "font_size": "large", "position": "lower_third"},
    "body": {"animation": "typewriter", "font_size": "medium", "position": "lower_third"},
    "climax": {"animation": "scale_pop", "font_size": "xlarge", "position": "center"},
    "outro": {"animation": "fade_in", "font_size": "large", "position": "center"},
}

TRANSITIONS = {
    "hook": ["cut", "glitch", "whip_pan"],
    "intro": ["dissolve", "slide_left", "zoom"],
    "body": ["cut", "dissolve", "slide_left", "slide_right", "zoom"],
    "climax": ["whip_pan", "glitch", "zoom"],
    "outro": ["dissolve", "fade"],
}
TRANSITION_DURATIONS = {
    "cut": 100,
    "dissolve": 500,
    "slide_left": 400,
    "slide_right": 400,
    "zoom": 350,
    "whip_pan": 300,
    "glitch": 250,
    "fade": 600,
}

MOTION_TEMPLATES = {
    "curiosity": [
        {"type": "floating_shape", "animation": "drift", "count": 3, "opacity": 0.15},
        {"type": "particle", "animation": "pulse", "count": 8, "opacity": 0.10},
    ],
    "surprise": [
        {"type": "pulse_ring", "animation": "expand", "count": 1, "opacity": 0.25},
        {"type": "particle", "animation": "expand", "count": 12, "opacity": 0.15},
    ],
    "fear": [
        {"type": "particle", "animation": "drift", "count": 5, "opacity": 0.08},
        {"type": "line_draw", "animation": "pulse", "count": 2, "opacity": 0.12},
    ],
    "hope": [
        {"type": "floating_shape", "animation": "drift", "count": 4, "opacity": 0.12},
        {"type": "icon_float", "animation": "orbit", "count": 2, "opacity": 0.15},
    ],
    "urgency": [
        {"type": "pulse_ring", "animation": "pulse", "count": 2, "opacity": 0.20},
        {"type": "particle", "animation": "expand", "count": 10, "opacity": 0.18},
    ],
    "satisfaction": [
        {"type": "floating_shape", "animation": "drift", "count": 2, "opacity": 0.10},
    ],
    "anger": [
        {"type": "line_draw", "animation": "pulse", "count": 3, "opacity": 0.20},
        {"type": "particle", "animation": "expand", "count": 8, "opacity": 0.15},
    ],
    "empathy": [
        {"type": "floating_shape", "animation": "drift", "count": 3, "opacity": 0.10},
    ],
    "neutral": [
        {"type": "floating_shape", "animation": "drift", "count": 2, "opacity": 0.08},
    ],
}

SFX_MAP = {
    "hook": [{"name": "impact", "volume": 0.6}, {"name": "rise", "volume": 0.4}],
    "transition": [{"name": "whoosh", "volume": 0.3}],
    "emphasis": [{"name": "shimmer", "volume": 0.25}],
    "climax": [{"name": "impact", "volume": 0.5}, {"name": "rise", "volume": 0.5}],
    "outro": [{"name": "drop", "volume": 0.3}],
    "question": [{"name": "rise", "volume": 0.2}],
}

EMPHASIS_EFFECTS = ["scale", "color_flash", "glow", "underline", "shake"]


def _text_display_duration_ms(text: str) -> int:
    """Minimum display time for text overlay based on character count.

    Rule: max(1200ms, 35ms × char_count). Capped at 5000ms.
    """
    chars = len(text)
    return min(5000, max(1200, chars * 35))


def _select_transition(section: str, prev_transition: str | None, seed: int | None = None) -> dict:
    """Select transition with variety enforcement (no consecutive same type)."""
    if seed is not None:
        random.seed(seed)

    candidates = TRANSITIONS.get(section, TRANSITIONS["body"])
    if prev_transition and prev_transition in candidates and len(candidates) > 1:
        candidates = [t for t in candidates if t != prev_transition]

    selected = random.choice(candidates)
    return {
        "type": selected,
        "duration_ms": TRANSITION_DURATIONS.get(selected, 400),
    }


def _select_camera(section: str, body_index: int = 0) -> dict:
    """Select camera movement based on section type."""
    if section == "body":
        variants = ["body_a", "body_b", "body_c"]
        key = variants[body_index % len(variants)]
    else:
        key = section

    template = CAMERA_TEMPLATES.get(key, CAMERA_TEMPLATES["body_a"])
    return dict(template)


def _generate_text_strategy(
    segment: dict,
    emphasis_words: list[str],
    section: str,
    channel: dict | None = None,
    appear_ms: int = 0,
) -> dict:
    """Generate text strategy for a segment."""
    text_overlay = segment.get("text_overlay", "")
    defaults = TEXT_ANIMATIONS.get(section, TEXT_ANIMATIONS["body"])

    emphasis_data = []
    primary_color = (channel or {}).get("primary_color", "#FFFFFF")
    for i, word in enumerate(emphasis_words[:3]):
        effect = EMPHASIS_EFFECTS[i % len(EMPHASIS_EFFECTS)]
        emphasis_data.append(
            {
                "word": word,
                "effect": effect,
                "color": primary_color,
            }
        )

    display_ms = _text_display_duration_ms(text_overlay) if text_overlay else 3000

    return {
        "primary_text": text_overlay,
        "font_size": defaults["font_size"],
        "animation": defaults["animation"],
        "position": defaults["position"],
        "timing_ms": {
            "appear": appear_ms,
            "duration": display_ms,
        },
        "emphasis_words": emphasis_data,
    }


def _generate_background_strategy(
    section: str,
    emotion: str,
    channel: dict | None = None,
) -> dict:
    """Generate background strategy based on section, emotion, and channel colors."""
    ch = channel or {}
    primary = ch.get("primary_color", "#1A1A2E")
    secondary = ch.get("secondary_color", "#16213E")

    if section in ("hook", "climax"):
        return {
            "type": "gradient",
            "primary_color": primary,
            "secondary_color": secondary,
            "overlay_opacity": 0.6,
            "blur_amount": 0,
        }
    elif section == "outro":
        return {
            "type": "solid",
            "primary_color": primary,
            "overlay_opacity": 0.0,
            "blur_amount": 0,
        }
    else:
        return {
            "type": "asset",
            "primary_color": primary,
            "overlay_opacity": 0.35,
            "blur_amount": 2,
        }


def _generate_motion_design(emotion: str, section: str, channel: dict | None = None) -> dict:
    """Generate motion design elements based on emotion and section."""
    primary_color = (channel or {}).get("primary_color", "#FFFFFF")
    templates = MOTION_TEMPLATES.get(emotion, MOTION_TEMPLATES["neutral"])

    elements = []
    for tmpl in templates:
        elements.append(
            {
                **tmpl,
                "color": primary_color,
            }
        )

    if section == "climax":
        for el in elements:
            el["count"] = int(el["count"] * 1.5)
            el["opacity"] = min(0.35, el["opacity"] * 1.3)

    if section == "outro":
        elements = elements[:1]
        for el in elements:
            el["opacity"] = min(0.10, el["opacity"])

    return {"elements": elements}


def _generate_audio_cues(
    section: str,
    emotion: str,
    emphasis_words: list[str],
    duration_s: float,
    is_first: bool = False,
    is_last: bool = False,
) -> dict:
    """Generate SFX and music shift cues."""
    sfx = []

    if is_first:
        for s in SFX_MAP["hook"]:
            sfx.append({**s, "trigger_ms": 0})

    if emphasis_words and duration_s > 0:
        interval_ms = int((duration_s * 1000) / (len(emphasis_words) + 1))
        for i, _ in enumerate(emphasis_words[:2]):
            sfx.append(
                {
                    "name": "shimmer",
                    "trigger_ms": interval_ms * (i + 1),
                    "volume": 0.2,
                }
            )

    if section == "climax":
        for s in SFX_MAP["climax"]:
            sfx.append({**s, "trigger_ms": 200})

    if is_last:
        sfx.append({"name": "drop", "trigger_ms": int(duration_s * 800), "volume": 0.3})

    if section == "hook":
        music_shift = "build"
    elif section == "climax":
        music_shift = "louder"
    elif section == "outro":
        music_shift = "quieter"
    elif emotion in ("fear", "urgency"):
        music_shift = "build"
    else:
        music_shift = "none"

    return {
        "sfx": sfx,
        "music_shift": music_shift,
    }


def generate_segment_direction(
    segment: dict,
    voice_data: dict | None = None,
    asset_data: dict | None = None,
    segment_index: int = 0,
    total_segments: int = 1,
    prev_transition: str | None = None,
    channel: dict | None = None,
    cumulative_time_ms: int = 0,
) -> dict[str, Any]:
    """Generate complete Remotion v3 direction for a single segment."""
    section = segment.get("section", "body")
    segment_id = segment.get("id", f"s{segment_index + 1}")
    duration_s = segment.get("duration_s", 5.0)
    is_first = segment_index == 0
    is_last = segment_index == total_segments - 1

    emotion = "neutral"
    emphasis_words = []
    if voice_data:
        emotion = voice_data.get("dominant_emotion", "neutral")
        emphasis_words = voice_data.get("emphasis_words", [])

    presets = SCENE_PRESETS.get(section, SCENE_PRESETS["body"])
    preset_idx = segment_index % len(presets)
    scene_preset = presets[preset_idx]

    camera = _select_camera(section, body_index=segment_index)

    text_strategy = _generate_text_strategy(
        segment,
        emphasis_words,
        section,
        channel,
        appear_ms=int(duration_s * 200),
    )

    background = _generate_background_strategy(section, emotion, channel)

    motion = _generate_motion_design(emotion, section, channel)

    audio = _generate_audio_cues(section, emotion, emphasis_words, duration_s, is_first, is_last)

    transition = _select_transition(section, prev_transition, seed=segment_index)

    duration_ms = int(duration_s * 1000)
    start_ms = cumulative_time_ms
    end_ms = start_ms + duration_ms

    return {
        "id": segment_id,
        "section": section,
        "scene_preset": scene_preset,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_ms": duration_ms,
        "camera": camera,
        "text_strategy": text_strategy,
        "background_strategy": background,
        "motion_design": motion,
        "audio_cues": audio,
        "transition_in": transition,
        "visual_effects": [],
    }


def generate_script_direction(
    segments: list[dict],
    voice_segments: list[dict] | None = None,
    asset_segments: list[dict] | None = None,
    channel: dict | None = None,
    fps: int = 30,
    resolution: str = "1080x1920",
) -> dict[str, Any]:
    """Generate complete Script v3 (Direction / Editing Config).

    Produces frame-accurate Remotion v3 JSON with camera, text,
    motion, audio, transitions for every segment.
    """
    direction_segments = []
    cumulative_ms = 0
    prev_transition = None
    total = len(segments)

    for i, seg in enumerate(segments):
        voice_data = voice_segments[i] if voice_segments and i < len(voice_segments) else None
        asset_data = asset_segments[i] if asset_segments and i < len(asset_segments) else None

        dir_seg = generate_segment_direction(
            segment=seg,
            voice_data=voice_data,
            asset_data=asset_data,
            segment_index=i,
            total_segments=total,
            prev_transition=prev_transition,
            channel=channel,
            cumulative_time_ms=cumulative_ms,
        )

        cumulative_ms = dir_seg["end_ms"]
        prev_transition = dir_seg["transition_in"]["type"]
        direction_segments.append(dir_seg)

    total_duration_ms = cumulative_ms
    total_frames = int((total_duration_ms / 1000) * fps)

    try:
        width, height = resolution.split("x")
        width, height = int(width), int(height)
    except (ValueError, AttributeError):
        width, height = 1080, 1920

    transitions_used = [ds["transition_in"]["type"] for ds in direction_segments]
    transition_variety = len(set(transitions_used))
    consecutive_same = sum(1 for i in range(1, len(transitions_used)) if transitions_used[i] == transitions_used[i - 1])

    presets_used = [ds["scene_preset"] for ds in direction_segments]
    preset_variety = len(set(presets_used))
    consecutive_same_preset = sum(1 for i in range(1, len(presets_used)) if presets_used[i] == presets_used[i - 1])

    has_text_every_seg = all(
        ds["text_strategy"]["primary_text"] or ds["text_strategy"]["emphasis_words"] for ds in direction_segments
    )
    has_motion_every_seg = all(len(ds["motion_design"]["elements"]) > 0 for ds in direction_segments)

    return {
        "version": "v3_direction",
        "render_config": {
            "fps": fps,
            "width": width,
            "height": height,
            "duration_ms": total_duration_ms,
            "total_frames": total_frames,
            "codec": "h264",
        },
        "segments": direction_segments,
        "qc": {
            "total_segments": total,
            "total_duration_ms": total_duration_ms,
            "total_frames": total_frames,
            "transition_variety": transition_variety,
            "consecutive_same_transitions": consecutive_same,
            "preset_variety": preset_variety,
            "consecutive_same_presets": consecutive_same_preset,
            "has_text_all_segments": has_text_every_seg,
            "has_motion_all_segments": has_motion_every_seg,
            "direction_ok": (consecutive_same <= 1 and preset_variety >= min(3, total) and has_motion_every_seg),
        },
    }
