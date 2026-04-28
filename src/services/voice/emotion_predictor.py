"""Voice Emotion Predictor — Local NLP-based emotion mapping to replace LLM calls.

Uses the script prosody engine hints when available, falls back to local
NLP emotion detection. This eliminates the GPT-4o-mini emotion mapping call
when prosody hints exist, saving ~$0.002-0.005 per video.

Intelligence cost: $0.00 — all computation is local.
"""
from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

# ── Emotion → TTS param mapping (mirrors prosody_engine.py in script service) ──
EMOTION_TTS_MAP: dict[str, dict] = {
    "curiosity": {"stability": 0.45, "similarity_boost": 0.70, "style": 0.50, "speed": 1.05},
    "excitement": {"stability": 0.35, "similarity_boost": 0.65, "style": 0.70, "speed": 1.15},
    "urgency": {"stability": 0.40, "similarity_boost": 0.75, "style": 0.65, "speed": 1.20},
    "empathy": {"stability": 0.55, "similarity_boost": 0.80, "style": 0.45, "speed": 0.95},
    "authority": {"stability": 0.60, "similarity_boost": 0.85, "style": 0.35, "speed": 0.90},
    "surprise": {"stability": 0.30, "similarity_boost": 0.65, "style": 0.75, "speed": 1.10},
    "concern": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.40, "speed": 0.95},
    "joy": {"stability": 0.35, "similarity_boost": 0.70, "style": 0.70, "speed": 1.10},
    "sadness": {"stability": 0.60, "similarity_boost": 0.80, "style": 0.30, "speed": 0.85},
    "anger": {"stability": 0.30, "similarity_boost": 0.70, "style": 0.80, "speed": 1.15},
    "fear": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.55, "speed": 1.05},
    "neutral": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.40, "speed": 1.00},
}

# ── Section-based pacing defaults ─────────────────────────
SECTION_PACING: dict[str, dict] = {
    "hook": {"speed_modifier": 1.05, "pause_after_ms": 400, "emphasis_boost": True},
    "intro": {"speed_modifier": 1.00, "pause_after_ms": 350, "emphasis_boost": False},
    "body": {"speed_modifier": 1.00, "pause_after_ms": 300, "emphasis_boost": False},
    "climax": {"speed_modifier": 0.95, "pause_after_ms": 500, "emphasis_boost": True},
    "conclusion": {"speed_modifier": 0.95, "pause_after_ms": 400, "emphasis_boost": False},
    "cta": {"speed_modifier": 1.05, "pause_after_ms": 200, "emphasis_boost": True},
}

# ── Keyword-based emotion detection ──────────────────────
EMOTION_KEYWORDS: dict[str, list[str]] = {
    "curiosity": ["why", "how", "what if", "wonder", "imagine", "secret", "hidden", "mystery", "question"],
    "excitement": ["amazing", "incredible", "breakthrough", "revolutionary", "game-changing", "exciting"],
    "urgency": ["now", "immediately", "critical", "emergency", "warning", "urgent", "hurry", "deadline"],
    "empathy": ["feel", "understand", "struggle", "pain", "difficult", "hard", "sorry", "relate"],
    "authority": ["research", "study", "scientists", "experts", "proven", "evidence", "data", "fact"],
    "surprise": ["shocking", "unexpected", "turns out", "actually", "plot twist", "believe it or not"],
    "concern": ["risk", "danger", "careful", "problem", "issue", "worry", "alarming", "concerning"],
    "joy": ["happy", "wonderful", "beautiful", "celebrate", "love", "fantastic", "delightful"],
}


def detect_sentence_emotion(text: str) -> str:
    """Detect dominant emotion from sentence text using keyword matching."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[emotion] = count

    if not scores:
        # Check punctuation cues
        if text.endswith("?"):
            return "curiosity"
        if text.endswith("!"):
            return "excitement"
        return "neutral"

    return max(scores, key=scores.get)


def detect_emphasis_words(text: str) -> list[str]:
    """Detect words that should be emphasized in speech."""
    words = text.split()
    emphasis = []
    for word in words:
        clean = re.sub(r'[^\w]', '', word)
        if not clean:
            continue
        # ALL CAPS words
        if clean.isupper() and len(clean) > 1:
            emphasis.append(clean)
        # Numbers and statistics
        elif any(c.isdigit() for c in clean):
            emphasis.append(clean)
        # Words with strong emotional connotation
        elif clean.lower() in {"never", "always", "every", "only", "most", "worst", "best",
                                "critical", "dangerous", "shocking", "proven", "secret",
                                "exactly", "specifically", "absolutely", "guaranteed"}:
            emphasis.append(clean)
    return emphasis[:5]  # Max 5 emphasis words per sentence


def predict_volume_shift(emotion: str, section: str) -> str:
    """Predict volume shift based on emotion and section."""
    loud_emotions = {"excitement", "urgency", "anger", "surprise"}
    quiet_emotions = {"empathy", "sadness", "concern"}

    if section == "hook":
        return "slightly_louder"
    if emotion in loud_emotions:
        return "louder"
    if emotion in quiet_emotions:
        return "softer"
    return "normal"


def map_prosody_hints_to_emotion(prosody_data: dict) -> dict:
    """Convert script prosody engine output to voice service emotion format.
    
    This is the key function that allows us to skip the LLM emotion mapping call.
    """
    tts_params = prosody_data.get("tts_params", {})
    emotion = prosody_data.get("dominant_emotion", "neutral")
    emphasis = prosody_data.get("emphasis_words", [])

    return {
        "stability": tts_params.get("stability", 0.50),
        "similarity_boost": tts_params.get("similarity_boost", 0.75),
        "style": tts_params.get("style", 0.40),
        "speed": tts_params.get("speed", 1.00),
        "emotion": emotion,
        "emphasis_words": emphasis,
        "pause_after_ms": tts_params.get("pause_after_ms", 300),
        "volume_shift": predict_volume_shift(emotion, prosody_data.get("section", "body")),
    }


def predict_emotions_for_sentences(sentences: list[dict], channel: dict) -> list[dict]:
    """Predict emotion parameters for each sentence using local NLP.
    
    This replaces the GPT-4o-mini emotion mapping call with $0.00 local processing.
    Quality is maintained by:
    1. Using prosody hints from script intelligence (already analyzed by spaCy + NLP)
    2. Falling back to keyword + punctuation emotion detection
    3. Section-aware pacing defaults from channel DNA
    """
    default_stability = float(channel.get("voice_stability", 0.50))
    default_similarity = float(channel.get("voice_similarity", 0.75))
    default_style = float(channel.get("voice_style", 0.40))

    results = []
    for sent in sentences:
        text = sent.get("text", "")
        section = sent.get("section", "body")
        prosody_hint = sent.get("prosody_hint", {})

        if prosody_hint and prosody_hint.get("tts_params"):
            # Use prosody hints from script intelligence (highest quality)
            emotion_data = map_prosody_hints_to_emotion(prosody_hint)
        else:
            # Local NLP fallback
            emotion = detect_sentence_emotion(text)
            emphasis = detect_emphasis_words(text)
            tts = EMOTION_TTS_MAP.get(emotion, EMOTION_TTS_MAP["neutral"])

            # Apply section pacing
            section_pacing = SECTION_PACING.get(section, SECTION_PACING["body"])
            speed = tts["speed"] * section_pacing["speed_modifier"]

            emotion_data = {
                "stability": tts["stability"],
                "similarity_boost": tts["similarity_boost"],
                "style": tts["style"],
                "speed": round(speed, 2),
                "emotion": emotion,
                "emphasis_words": emphasis,
                "pause_after_ms": section_pacing["pause_after_ms"],
                "volume_shift": predict_volume_shift(emotion, section),
            }

        # Blend with channel defaults (30% channel identity, 70% predicted)
        emotion_data["stability"] = round(
            emotion_data["stability"] * 0.7 + default_stability * 0.3, 3)
        emotion_data["similarity_boost"] = round(
            emotion_data["similarity_boost"] * 0.7 + default_similarity * 0.3, 3)
        emotion_data["style"] = round(
            emotion_data["style"] * 0.7 + default_style * 0.3, 3)

        results.append(emotion_data)

    return results
