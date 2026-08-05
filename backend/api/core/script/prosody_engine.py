"""Prosody Engine — Script v1 (Voice Over) generator.

Transforms the base script into a voice-optimized version with:
- SSML markup for any TTS provider (provider-agnostic)
- Per-sentence emotion tags (from NLP emotion lexicon)
- Emphasis word detection (TF-IDF + POS rules)
- Pace marks (WPM mapping per sentence)
- Pause insertion (after punctuation, key statements, section transitions)
- Break long sentences at natural breath points
- Alignment marks for A/V sync
- TTS parameter mapping (stability, similarity_boost, style, speed)

All computation is local. Zero API cost.
"""

from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import structlog

from services_api.script.script_analyzer import (
    detect_emotions,
    detect_emphasis_words,
    estimate_speaking_duration,
)

logger = structlog.get_logger()

SECTION_PROSODY = {
    "hook": {
        "base_speed": 1.15,
        "stability": 0.40,
        "style": 0.70,
        "similarity_boost": 0.75,
        "base_volume": "medium",
        "pause_after_ms": 300,
    },
    "intro": {
        "base_speed": 1.05,
        "stability": 0.55,
        "style": 0.50,
        "similarity_boost": 0.80,
        "base_volume": "medium",
        "pause_after_ms": 400,
    },
    "body": {
        "base_speed": 1.00,
        "stability": 0.55,
        "style": 0.45,
        "similarity_boost": 0.80,
        "base_volume": "medium",
        "pause_after_ms": 350,
    },
    "climax": {
        "base_speed": 0.90,
        "stability": 0.35,
        "style": 0.75,
        "similarity_boost": 0.70,
        "base_volume": "loud",
        "pause_after_ms": 600,
    },
    "outro": {
        "base_speed": 0.95,
        "stability": 0.65,
        "style": 0.40,
        "similarity_boost": 0.85,
        "base_volume": "soft",
        "pause_after_ms": 500,
    },
}

EMOTION_TTS_MAP = {
    "curiosity": {"stability": 0.45, "style": 0.55, "speed_mod": 1.05, "pitch": "medium"},
    "surprise": {"stability": 0.35, "style": 0.70, "speed_mod": 1.10, "pitch": "high"},
    "fear": {"stability": 0.30, "style": 0.65, "speed_mod": 0.95, "pitch": "low"},
    "hope": {"stability": 0.55, "style": 0.50, "speed_mod": 1.00, "pitch": "medium"},
    "urgency": {"stability": 0.35, "style": 0.60, "speed_mod": 1.20, "pitch": "high"},
    "satisfaction": {"stability": 0.60, "style": 0.40, "speed_mod": 0.95, "pitch": "medium"},
    "anger": {"stability": 0.30, "style": 0.75, "speed_mod": 1.05, "pitch": "low"},
    "empathy": {"stability": 0.55, "style": 0.50, "speed_mod": 0.90, "pitch": "medium"},
    "neutral": {"stability": 0.55, "style": 0.40, "speed_mod": 1.00, "pitch": "medium"},
}

PAUSE_RULES = {
    "period": 400,
    "exclamation": 300,
    "question": 350,
    "comma": 150,
    "semicolon": 250,
    "colon": 200,
    "dash": 200,
    "ellipsis": 500,
    "paragraph": 700,
}


async def analyze_sentence_prosody(
    sentence: str,
    section: str = "body",
    prev_emotion: str = "neutral",
) -> dict[str, Any]:
    """Generate prosody data for a single sentence.

    Returns: emotion, TTS params, emphasis words, SSML, timing.
    """
    emotions = await detect_emotions(sentence)
    emphasis = await detect_emphasis_words(sentence, top_n=3)
    section_defaults = SECTION_PROSODY.get(section, SECTION_PROSODY["body"])
    emotion = emotions["dominant_emotion"]
    emotion_params = EMOTION_TTS_MAP.get(emotion, EMOTION_TTS_MAP["neutral"])

    speed = section_defaults["base_speed"] * emotion_params["speed_mod"]
    stability = section_defaults["stability"] * 0.5 + emotion_params["stability"] * 0.5
    style = section_defaults["style"] * 0.4 + emotion_params["style"] * 0.6
    similarity_boost = section_defaults["similarity_boost"]

    word_count = len(sentence.split())
    if word_count <= 5:
        speed *= 0.85
    elif word_count <= 8:
        speed *= 0.92

    speed = round(min(2.0, max(0.5, speed)), 2)

    pause_ms = section_defaults["pause_after_ms"]
    if sentence.rstrip().endswith("?"):
        pause_ms = max(pause_ms, PAUSE_RULES["question"])
    elif sentence.rstrip().endswith("!"):
        pause_ms = max(pause_ms, PAUSE_RULES["exclamation"])
    elif sentence.rstrip().endswith("..."):
        pause_ms = max(pause_ms, PAUSE_RULES["ellipsis"])

    if emotion != prev_emotion and prev_emotion != "neutral":
        pause_ms += 200

    volume = section_defaults["base_volume"]
    if emotion in ("urgency", "anger", "surprise"):
        volume = "louder"
    elif emotion in ("empathy", "hope") and section == "outro":
        volume = "softer"

    duration_s = estimate_speaking_duration(sentence, wpm=int(150 * speed))

    return {
        "text": sentence,
        "emotion": emotion,
        "emotion_scores": emotions["scores"],
        "emphasis_words": [e["word"] for e in emphasis],
        "tts_params": {
            "stability": round(stability, 2),
            "similarity_boost": round(similarity_boost, 2),
            "style": round(style, 2),
            "speed": speed,
        },
        "volume_shift": volume,
        "pause_after_ms": pause_ms,
        "pitch": emotion_params["pitch"],
        "duration_s": round(duration_s, 2),
    }


def generate_ssml_sentence(prosody_data: dict) -> str:
    """Generate SSML 1.1 for a single sentence."""
    text = prosody_data["text"]
    speed = prosody_data["tts_params"]["speed"]
    pitch = prosody_data["pitch"]
    emphasis_words = set(prosody_data.get("emphasis_words", []))
    pause_ms = prosody_data["pause_after_ms"]

    if speed <= 0.75:
        rate = "slow"
    elif speed <= 0.95:
        rate = "medium"
    elif speed <= 1.15:
        rate = "default"
    else:
        rate = "fast"

    words = text.split()
    ssml_words = []
    for word in words:
        clean = re.sub(r"[^\w]", "", word).lower()
        if any(clean == ew.lower() for ew in emphasis_words):
            ssml_words.append(f'<emphasis level="strong">{xml_escape(word)}</emphasis>')
        else:
            ssml_words.append(xml_escape(word))

    inner = " ".join(ssml_words)
    ssml = f'<prosody rate="{rate}" pitch="{pitch}">{inner}</prosody>'

    if pause_ms > 0:
        ssml += f'<break time="{pause_ms}ms"/>'

    return ssml


async def generate_segment_voice(segment: dict, segment_index: int = 0) -> dict[str, Any]:
    """Generate full voice markup for a script segment.

    Returns: sentence-level prosody, composite SSML, timing data, TTS params.
    """
    narration = segment.get("narration", "")
    section = segment.get("section", "body")
    segment_id = segment.get("id", f"s{segment_index + 1}")

    sentences = re.split(r"(?<=[.!?])\s+", narration)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [narration] if narration.strip() else []

    sentence_prosody = []
    ssml_parts = []
    total_duration = 0.0
    prev_emotion = "neutral"

    for sent in sentences:
        prosody = await analyze_sentence_prosody(sent, section, prev_emotion)
        sentence_prosody.append(prosody)
        ssml_parts.append(generate_ssml_sentence(prosody))
        total_duration += prosody["duration_s"] + (prosody["pause_after_ms"] / 1000)
        prev_emotion = prosody["emotion"]

    ssml_body = "\n    ".join(ssml_parts)
    full_ssml = (
        f'<speak>\n  <mark name="{segment_id}_start"/>\n    {ssml_body}\n  <mark name="{segment_id}_end"/>\n</speak>'
    )

    if sentence_prosody:
        weights = [len(sp["text"].split()) for sp in sentence_prosody]
        total_w = max(sum(weights), 1)
        avg_params = {
            "stability": sum(sp["tts_params"]["stability"] * w for sp, w in zip(sentence_prosody, weights)) / total_w,
            "similarity_boost": sum(
                sp["tts_params"]["similarity_boost"] * w for sp, w in zip(sentence_prosody, weights)
            )
            / total_w,
            "style": sum(sp["tts_params"]["style"] * w for sp, w in zip(sentence_prosody, weights)) / total_w,
            "speed": sum(sp["tts_params"]["speed"] * w for sp, w in zip(sentence_prosody, weights)) / total_w,
        }
        avg_params = {k: round(v, 2) for k, v in avg_params.items()}
    else:
        avg_params = {"stability": 0.55, "similarity_boost": 0.80, "style": 0.45, "speed": 1.0}

    all_emphasis = []
    for sp in sentence_prosody:
        all_emphasis.extend(sp["emphasis_words"])

    emotion_counts: dict[str, int] = {}
    for sp in sentence_prosody:
        e = sp["emotion"]
        emotion_counts[e] = emotion_counts.get(e, 0) + len(sp["text"].split())
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

    return {
        "segment_id": segment_id,
        "section": section,
        "sentences": sentence_prosody,
        "ssml": full_ssml,
        "tts_params": avg_params,
        "emphasis_words": list(dict.fromkeys(all_emphasis)),
        "dominant_emotion": dominant_emotion,
        "total_duration_s": round(total_duration, 2),
        "sentence_count": len(sentences),
    }


async def generate_script_voice(segments: list[dict], channel: dict | None = None) -> dict[str, Any]:
    """Generate complete Script v1 (Voice Over version).

    Produces per-segment and per-sentence prosody data, SSML,
    TTS parameters, emotion curves, timing, and alignment marks.
    """
    voice_segments = []
    cumulative_time = 0.0

    for i, seg in enumerate(segments):
        voice_seg = await generate_segment_voice(seg, i)

        voice_seg["start_time_s"] = round(cumulative_time, 2)
        cumulative_time += voice_seg["total_duration_s"]
        voice_seg["end_time_s"] = round(cumulative_time, 2)

        voice_segments.append(voice_seg)

    full_ssml_parts = [vs["ssml"] for vs in voice_segments]
    full_ssml = "\n".join(full_ssml_parts)

    emotion_curve = [
        {
            "segment_id": vs["segment_id"],
            "emotion": vs["dominant_emotion"],
            "start_s": vs["start_time_s"],
            "end_s": vs["end_time_s"],
        }
        for vs in voice_segments
    ]

    total_sentences = sum(vs["sentence_count"] for vs in voice_segments)
    complete_sentences = sum(
        1 for vs in voice_segments for sp in vs["sentences"] if sp["emotion"] != "neutral" or sp["emphasis_words"]
    )
    prosody_coverage = complete_sentences / max(total_sentences, 1)

    total_duration = voice_segments[-1]["end_time_s"] if voice_segments else 0

    return {
        "version": "v1_voice",
        "segments": voice_segments,
        "full_ssml": full_ssml,
        "emotion_curve": emotion_curve,
        "total_duration_s": round(total_duration, 2),
        "total_sentences": total_sentences,
        "prosody_coverage": round(prosody_coverage, 3),
        "qc": {
            "prosody_coverage": round(prosody_coverage, 3),
            "coverage_ok": prosody_coverage >= 0.85,
            "total_emphasis_words": sum(len(vs["emphasis_words"]) for vs in voice_segments),
            "emotion_variety": len(set(vs["dominant_emotion"] for vs in voice_segments)),
        },
    }
