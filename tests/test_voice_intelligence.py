"""Unit tests for Voice Service intelligence modules.

Tests: emotion_predictor, audio_quality_scorer, voice_style_learner
"""
from __future__ import annotations

import pytest
import numpy as np

from services_api.voice.emotion_predictor import (
    detect_sentence_emotion,
    detect_emphasis_words,
    predict_volume_shift,
    map_prosody_hints_to_emotion,
    predict_emotions_for_sentences,
    EMOTION_TTS_MAP,
    SECTION_PACING,
)
from services_api.voice.audio_quality_scorer import _quick_audio_stats



class TestDetectSentenceEmotion:
    def test_curiosity_keyword(self):
        assert detect_sentence_emotion("Why do people wonder about this?") == "curiosity"

    def test_excitement_keyword(self):
        assert detect_sentence_emotion("This is an amazing breakthrough!") == "excitement"

    def test_urgency_keyword(self):
        assert detect_sentence_emotion("You need to act now immediately") == "urgency"

    def test_authority_keyword(self):
        assert detect_sentence_emotion("Research and data have proven this") == "authority"

    def test_empathy_keyword(self):
        assert detect_sentence_emotion("I understand your struggle and pain") == "empathy"

    def test_surprise_keyword(self):
        assert detect_sentence_emotion("Shocking — it turns out this was wrong") == "surprise"

    def test_neutral_no_keywords(self):
        assert detect_sentence_emotion("The cat sat on the mat") == "neutral"

    def test_question_mark_fallback(self):
        assert detect_sentence_emotion("Is this correct?") == "curiosity"

    def test_exclamation_fallback(self):
        assert detect_sentence_emotion("This is great!") == "excitement"

    def test_empty_string(self):
        assert detect_sentence_emotion("") == "neutral"

    def test_multiple_emotions_picks_strongest(self):
        result = detect_sentence_emotion("Why is this so amazing and incredible?")
        assert result in ("excitement", "curiosity")


class TestDetectEmphasisWords:
    def test_all_caps(self):
        emphasis = detect_emphasis_words("This is VERY IMPORTANT stuff")
        assert "VERY" in emphasis
        assert "IMPORTANT" in emphasis

    def test_numbers(self):
        emphasis = detect_emphasis_words("About 90% of people fail within 3 days")
        number_words = [w for w in emphasis if any(c.isdigit() for c in w)]
        assert len(number_words) >= 1

    def test_strong_words(self):
        emphasis = detect_emphasis_words("This is absolutely the best and only way")
        assert any(w.lower() in {"absolutely", "best", "only"} for w in emphasis)

    def test_max_five(self):
        emphasis = detect_emphasis_words(
            "NEVER ALWAYS EVERY ONLY MOST WORST BEST CRITICAL DANGEROUS SHOCKING")
        assert len(emphasis) <= 5

    def test_empty_string(self):
        assert detect_emphasis_words("") == []


class TestPredictVolumeShift:
    def test_hook_section(self):
        assert predict_volume_shift("neutral", "hook") == "slightly_louder"

    def test_excitement_louder(self):
        assert predict_volume_shift("excitement", "body") == "louder"

    def test_empathy_softer(self):
        assert predict_volume_shift("empathy", "body") == "softer"

    def test_neutral_normal(self):
        assert predict_volume_shift("neutral", "body") == "normal"


class TestMapProsodyHints:
    def test_maps_tts_params(self):
        prosody = {
            "tts_params": {"stability": 0.45, "similarity_boost": 0.70, "style": 0.50, "speed": 1.05},
            "dominant_emotion": "curiosity",
            "emphasis_words": ["why", "secret"],
            "section": "hook",
        }
        result = map_prosody_hints_to_emotion(prosody)
        assert result["emotion"] == "curiosity"
        assert result["stability"] == 0.45
        assert result["speed"] == 1.05
        assert "why" in result["emphasis_words"]

    def test_defaults_when_missing(self):
        result = map_prosody_hints_to_emotion({})
        assert result["emotion"] == "neutral"
        assert result["stability"] == 0.50


class TestPredictEmotionsForSentences:
    def test_uses_prosody_hint_when_available(self, sample_channel):
        sentences = [{
            "text": "This is a test",
            "section": "hook",
            "prosody_hint": {
                "tts_params": {"stability": 0.35, "similarity_boost": 0.65, "style": 0.70, "speed": 1.15},
                "dominant_emotion": "excitement",
                "emphasis_words": ["test"],
            },
        }]
        results = predict_emotions_for_sentences(sentences, sample_channel)
        assert len(results) == 1
        assert results[0]["emotion"] == "excitement"

    def test_falls_back_to_keyword_detection(self, sample_channel):
        sentences = [{"text": "Why does this happen?", "section": "body"}]
        results = predict_emotions_for_sentences(sentences, sample_channel)
        assert len(results) == 1
        assert results[0]["emotion"] == "curiosity"

    def test_blends_channel_defaults(self, sample_channel):
        sentences = [{"text": "Normal text here", "section": "body"}]
        results = predict_emotions_for_sentences(sentences, sample_channel)
        assert 0.0 <= results[0]["stability"] <= 1.0

    def test_empty_list(self, sample_channel):
        assert predict_emotions_for_sentences([], sample_channel) == []


class TestEmotionTTSMap:
    def test_all_emotions_have_required_keys(self):
        for emotion, params in EMOTION_TTS_MAP.items():
            assert "stability" in params, f"{emotion} missing stability"
            assert "similarity_boost" in params, f"{emotion} missing similarity_boost"
            assert "style" in params, f"{emotion} missing style"
            assert "speed" in params, f"{emotion} missing speed"

    def test_values_in_valid_range(self):
        for emotion, params in EMOTION_TTS_MAP.items():
            assert 0 <= params["stability"] <= 1, f"{emotion} stability out of range"
            assert 0 <= params["similarity_boost"] <= 1, f"{emotion} similarity_boost out of range"
            assert 0 <= params["style"] <= 1, f"{emotion} style out of range"
            assert 0.5 <= params["speed"] <= 2.0, f"{emotion} speed out of range"


class TestSectionPacing:
    def test_all_sections_present(self):
        expected = {"hook", "intro", "body", "climax", "conclusion", "cta"}
        assert set(SECTION_PACING.keys()) == expected



class TestQuickAudioStats:
    def test_too_short(self):
        result = _quick_audio_stats(b"short")
        assert result["valid"] is False

    def test_empty(self):
        result = _quick_audio_stats(b"")
        assert result["valid"] is False

    def test_valid_mp3_header(self):
        audio = b"ID3" + b"\x00" * 200
        result = _quick_audio_stats(audio)
        assert result["valid"] is True
        assert result["format_ok"] is True
        assert result["size_kb"] > 0

    def test_unknown_format(self):
        audio = b"\x00" * 200
        result = _quick_audio_stats(audio)
        assert result["valid"] is True
        assert result["format_ok"] is False
