"""Unit tests for Assets Service intelligence modules.

Tests: query_optimizer (pure functions + DB-dependent with mocks)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.services.assets.query_optimizer import (
    optimize_query,
    score_asset_relevance,
    _query_hash,
    MOOD_SYNONYMS,
    SHOT_QUALITY_TERMS,
)


# Query Hash

class TestQueryHash:
    def test_deterministic(self):
        assert _query_hash("test query") == _query_hash("test query")

    def test_case_insensitive(self):
        assert _query_hash("Test Query") == _query_hash("test query")

    def test_strips_whitespace(self):
        assert _query_hash("  test query  ") == _query_hash("test query")

    def test_different_queries_different_hash(self):
        assert _query_hash("query one") != _query_hash("query two")


# Optimize Query

class TestOptimizeQuery:
    def test_uses_primary_query_from_script_intel(self):
        segment = {
            "primary_query": "futuristic city skyline",
            "alternate_queries": ["neon cityscape"],
            "shot_type": "wide",
            "mood": {"name": "tech"},
        }
        result = optimize_query(segment)
        assert len(result["queries"]) >= 1
        assert "futuristic city skyline" in result["queries"][0]

    def test_adds_shot_qualifiers(self):
        segment = {
            "primary_query": "sunset beach",
            "shot_type": "aerial",
            "mood": {},
        }
        result = optimize_query(segment)
        # Aerial qualifier should be in the first query
        assert any("aerial" in q or "drone" in q for q in result["queries"])

    def test_expands_mood_synonyms(self):
        segment = {
            "primary_query": "mountain landscape",
            "shot_type": "wide",
            "mood": {"name": "calm"},
        }
        result = optimize_query(segment)
        # Should have synonym-expanded queries
        assert len(result["queries"]) > 1

    def test_falls_back_to_b_roll_keywords(self):
        segment = {
            "b_roll_keywords": ["confused person", "question mark"],
            "asset_suggestions": [],
            "scene_direction": "",
        }
        result = optimize_query(segment)
        assert len(result["queries"]) >= 1
        assert "confused" in result["queries"][0].lower() or "person" in result["queries"][0].lower()

    def test_falls_back_to_scene_direction(self):
        segment = {
            "b_roll_keywords": [],
            "asset_suggestions": [],
            "scene_direction": "Close up of a scientist in a lab",
        }
        result = optimize_query(segment)
        assert len(result["queries"]) >= 1

    def test_empty_segment_returns_no_queries(self):
        result = optimize_query({})
        assert result["queries"] == []

    def test_max_five_queries(self):
        segment = {
            "primary_query": "test",
            "alternate_queries": ["a", "b", "c", "d", "e", "f"],
            "shot_type": "medium",
            "mood": {"name": "energetic"},
        }
        result = optimize_query(segment)
        assert len(result["queries"]) <= 5

    def test_includes_primary_hash(self):
        segment = {"primary_query": "test query", "shot_type": "medium", "mood": {}}
        result = optimize_query(segment)
        assert "primary_hash" in result
        assert len(result["primary_hash"]) == 16


# Score Asset Relevance

class TestScoreAssetRelevance:
    def test_high_relevance_clip(self):
        clip = {"tags": "futuristic city skyline neon night", "height": 1080, "duration": 10, "license": "free"}
        score = score_asset_relevance(clip, "futuristic city skyline")
        assert score >= 7.0

    def test_low_relevance_clip(self):
        clip = {"tags": "cute puppy playing ball", "height": 480, "duration": 1, "license": "premium"}
        score = score_asset_relevance(clip, "futuristic city skyline")
        assert score <= 5.0

    def test_resolution_bonus_1080(self):
        clip_1080 = {"tags": "test", "height": 1080, "duration": 5}
        clip_480 = {"tags": "test", "height": 480, "duration": 5}
        assert score_asset_relevance(clip_1080, "test") > score_asset_relevance(clip_480, "test")

    def test_short_duration_penalty(self):
        clip_long = {"tags": "test", "height": 720, "duration": 10}
        clip_short = {"tags": "test", "height": 720, "duration": 1}
        assert score_asset_relevance(clip_long, "test") > score_asset_relevance(clip_short, "test")

    def test_score_clamped_1_to_10(self):
        clip = {"tags": "a b c d e f g h i j k l m n", "height": 4320, "duration": 60, "license": "free"}
        score = score_asset_relevance(clip, "a b c d e f g h i j")
        assert 1.0 <= score <= 10.0

    def test_empty_clip(self):
        score = score_asset_relevance({}, "test query")
        assert 1.0 <= score <= 10.0


# Mood Synonyms

class TestMoodSynonyms:
    def test_known_moods_have_synonyms(self):
        assert len(MOOD_SYNONYMS["calm"]) >= 2
        assert len(MOOD_SYNONYMS["tech"]) >= 2

    def test_synonyms_are_strings(self):
        for mood, syns in MOOD_SYNONYMS.items():
            for s in syns:
                assert isinstance(s, str), f"{mood} has non-string synonym"
