"""Shared pytest fixtures for intelligence module tests.

Mocks DB pool, Redis, and external services so tests run without infrastructure.
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.db


@pytest.fixture(scope="session", autouse=True)
def _test_jwt_secret():
    """Provide a non-insecure JWT secret for the full test session.

    The production _jwt_secret() now rejects the 'dev-insecure-change-me'
    default so tests must supply a deterministic-but-safe value.
    """
    os.environ.setdefault("AUTH_JWT_SECRET", "ci-test-jwt-secret-not-for-production-use")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class FakeRecord(dict):
    """Dict subclass that supports attribute access like asyncpg.Record."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class FakeConn:
    """Asyncpg connection mock — yielded by FakePool.acquire()."""

    def __init__(self):
        self.execute = AsyncMock(return_value=None)
        self.executemany = AsyncMock()
        self.fetchrow = AsyncMock(return_value=None)
        self.fetchval = AsyncMock(return_value=0)
        self.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def transaction(self):
        yield self


class FakePool:
    """Minimal asyncpg pool mock."""

    def __init__(self):
        self.execute = AsyncMock(return_value="INSERT 0 1")
        self.executemany = AsyncMock()
        self.fetchrow = AsyncMock(return_value=None)
        self.fetchval = AsyncMock(return_value=0)
        self.fetch = AsyncMock(return_value=[])
        self.conn = FakeConn()

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.fixture
def mock_pool():
    pool = FakePool()
    original = core.db.get_pool
    targets = ["core.db.get_pool"]
    for _name, _mod in list(sys.modules.items()):
        if _mod is None or _name == "core.db":
            continue
        try:
            _candidate = getattr(_mod, "get_pool", None)
        except Exception:
            continue
        if _candidate is original:
            targets.append(f"{_name}.get_pool")
    started = []
    for _t in targets:
        _p = patch(_t, new_callable=AsyncMock, return_value=pool)
        try:
            _p.start()
            started.append(_p)
        except (AttributeError, ModuleNotFoundError):
            pass
    try:
        yield pool
    finally:
        for _p in started:
            try:
                _p.stop()
            except RuntimeError:
                pass


@pytest.fixture
def mock_db_pool(mock_pool):
    """Like mock_pool, but ALSO patches the module-level ``get_pool`` re-imports
    in v2 routers (workspace, auth) so direct-call unit tests bypass the real pool.
    """
    targets = [
        "services_api.dashboard.v2.workspace.get_pool",
        "services_api.dashboard.v2.auth.get_pool",
        "services_api.dashboard.v2._deps.get_pool",
    ]
    patches = [patch(t, new_callable=AsyncMock, return_value=mock_pool) for t in targets]
    for p in patches:
        try:
            p.start()
        except (AttributeError, ModuleNotFoundError):
            pass
    yield mock_pool
    for p in patches:
        try:
            p.stop()
        except RuntimeError:
            pass


@pytest.fixture
def fake_record():
    """Factory for creating FakeRecord instances."""
    def _make(**kwargs):
        return FakeRecord(kwargs)
    return _make


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
