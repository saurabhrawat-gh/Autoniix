"""Shared pytest fixtures for intelligence module tests.

Mocks DB pool, Redis, and external services so tests run without infrastructure.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Event loop
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock DB pool
class FakeRecord(dict):
    """Dict subclass that supports attribute access like asyncpg.Record."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class FakePool:
    """Minimal asyncpg pool mock."""

    def __init__(self):
        self.execute = AsyncMock(return_value="INSERT 0 1")
        self.executemany = AsyncMock()
        self.fetchrow = AsyncMock(return_value=None)
        self.fetchval = AsyncMock(return_value=0)
        self.fetch = AsyncMock(return_value=[])


@pytest.fixture
def mock_pool():
    pool = FakePool()
    with patch("src.db.get_pool", new_callable=AsyncMock, return_value=pool):
        yield pool


@pytest.fixture
def fake_record():
    """Factory for creating FakeRecord instances."""
    def _make(**kwargs):
        return FakeRecord(kwargs)
    return _make


# Sample data factories
@pytest.fixture
def sample_channel():
    return {
        "channel_id": "CH_test_001",
        "channel_name": "Test Channel",
        "niche": "tech",
        "content_mode": "short",
        "voice_id": "voice_001",
        "voice_stability": "0.50",
        "voice_similarity": "0.75",
        "voice_style": "0.40",
        "brand_config": {},
    }


@pytest.fixture
def sample_segments():
    return [
        {
            "id": "seg_001",
            "section": "hook",
            "narration": "Why do 90% of people get this WRONG?",
            "emotion": "curiosity",
            "emphasis_words": ["90%", "WRONG"],
            "scene_direction": "Close up of person looking confused",
            "b_roll_keywords": ["confused person", "question mark"],
            "asset_suggestions": ["stock confused face"],
        },
        {
            "id": "seg_002",
            "section": "body",
            "narration": "Scientists have proven that this simple technique works.",
            "emotion": "authority",
            "emphasis_words": ["proven", "simple"],
            "scene_direction": "Wide shot of laboratory",
            "b_roll_keywords": ["laboratory", "science"],
            "asset_suggestions": ["stock lab footage"],
        },
        {
            "id": "seg_003",
            "section": "cta",
            "narration": "Subscribe now if you want more secrets like this!",
            "emotion": "excitement",
            "emphasis_words": ["Subscribe", "secrets"],
            "scene_direction": "Subscribe button animation",
            "b_roll_keywords": ["subscribe", "bell"],
            "asset_suggestions": ["subscribe animation"],
        },
    ]


@pytest.fixture
def sample_direction_v3():
    return {
        "meta": {
            "title": "Test Video",
            "aspect_ratio": "9:16",
            "fps": 30,
            "duration_target_seconds": 45,
        },
        "segments": [
            {
                "id": "seg_001",
                "section": "hook",
                "duration_ms": 5000,
                "scene_preset": "dramatic_zoom",
                "camera": {"type": "zoom_in", "speed": "fast"},
                "motion_design": {"elements": [{"type": "text_pop"}, {"type": "emoji"}]},
                "visual_effects": ["vignette"],
                "audio_cues": {"sfx": ["whoosh"]},
                "text_strategy": {"text": "Why 90% get this WRONG"},
            },
            {
                "id": "seg_002",
                "section": "body",
                "duration_ms": 30000,
                "scene_preset": "clean_info",
                "camera": {"type": "static", "speed": "normal"},
                "motion_design": {"elements": [{"type": "chart"}]},
                "visual_effects": [],
                "audio_cues": {"sfx": []},
            },
            {
                "id": "seg_003",
                "section": "cta",
                "duration_ms": 5000,
                "scene_preset": "cta_popup",
                "camera": {"type": "static", "speed": "normal"},
                "motion_design": {"elements": [{"type": "subscribe_button"}]},
                "visual_effects": ["glow"],
                "audio_cues": {"sfx": ["ding"]},
            },
        ],
        "global_overlays": [{"type": "watermark"}],
    }
