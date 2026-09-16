"""Tier 2 orchestration tests — Temporal + notification hardening.

Covers the changes shipped in the "Tier 2" pass:
  * ``common.emit_job_event`` — Postgres write + Redis Streams dual-write
    + dedup guard
  * ``common.acquire_channel_lock_v2`` / ``release_channel_lock`` —
    fencing token round-trip
  * ``common.save_checkpoint_data`` / ``load_checkpoint_data`` —
    envelope + checksum + size cap
  * ``notification-dispatcher`` — exponential backoff + dead-letter
  * ``sentry-agent`` — daily quota + approval gate

All tests are pure-logic (mocked Redis / Postgres / storage) so they
run in CI without infrastructure.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# The temporal workers module directory is renamed to ``temporal_workers``
# inside the Dockerfile. For local tests we import via its on-disk name
# (``workers``) by adding its parent to sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKERS_PARENT = _REPO_ROOT / "backend" / "workers" / "temporal"
if str(_WORKERS_PARENT) not in sys.path:
    sys.path.insert(0, str(_WORKERS_PARENT))


# ──────────────────────── common.emit_job_event ────────────────────────


class _FakeRedis:
    """Minimal Redis mock capturing xadd/publish/set(nx=True)."""

    def __init__(self, first_call_wins=True):
        self._first_wins = first_call_wins
        self._seen = set()
        self.xadd_calls = []
        self.publish_calls = []

    async def set(self, key, value, nx=False, ex=None):
        if not nx:
            return True
        if key in self._seen:
            return None
        self._seen.add(key)
        return True

    async def xadd(self, key, fields, maxlen=None, approximate=True):
        self.xadd_calls.append((key, fields))
        return f"{len(self.xadd_calls)}-0"

    async def publish(self, channel, payload):
        self.publish_calls.append((channel, payload))
        return 1

    async def delete(self, *keys):
        for k in keys:
            self._seen.discard(k)
        return len(keys)

    async def eval(self, script, numkeys, *args):
        # Simplified: assume the fencing token matches on first call
        return 1

    async def expire(self, key, ttl):
        return 1

    async def incr(self, key):
        self._seen.add(key)
        return 1

    async def aclose(self):
        pass


def _unwrap(fn):
    return fn.__wrapped__ if hasattr(fn, "__wrapped__") else fn


@pytest.mark.asyncio
async def test_emit_job_event_writes_postgres_and_stream():
    from workers.activities.common import emit_job_event

    from tests.conftest import FakePool

    fake_redis = _FakeRedis()
    fake_pool = FakePool()
    fn = _unwrap(emit_job_event)
    with (
        patch(
            "workers.activities.common.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ),
        patch("workers.activities.common.get_pool", new=AsyncMock(return_value=fake_pool)),
    ):
        await fn("vid_1", "ch_1", "script", "done", {"cost": 0.10}, 0.10)

    assert fake_pool.execute.await_count == 1
    assert len(fake_redis.xadd_calls) == 1
    stream_key, fields = fake_redis.xadd_calls[0]
    assert stream_key == "stream:jobs:vid_1"
    assert fields["phase"] == "script"
    assert fields["status"] == "done"
    assert len(fake_redis.publish_calls) == 1


@pytest.mark.asyncio
async def test_emit_job_event_dedup_skips_duplicate():
    from workers.activities.common import emit_job_event

    from tests.conftest import FakePool

    fake_redis = _FakeRedis()
    fake_pool = FakePool()
    fn = _unwrap(emit_job_event)
    with (
        patch(
            "workers.activities.common.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ),
        patch("workers.activities.common.get_pool", new=AsyncMock(return_value=fake_pool)),
    ):
        await fn("vid_2", "ch_1", "script", "done", {"x": 1}, 0)
        await fn("vid_2", "ch_1", "script", "done", {"x": 1}, 0)

    assert fake_pool.execute.await_count == 1
    assert len(fake_redis.xadd_calls) == 1


# ──────────────────────── channel lock fencing ────────────────────────


@pytest.mark.asyncio
async def test_acquire_lock_v2_returns_token():
    from workers.activities.common import acquire_channel_lock_v2

    fake_redis = _FakeRedis()
    fn = _unwrap(acquire_channel_lock_v2)
    with patch("workers.activities.common.get_redis", new=AsyncMock(return_value=fake_redis)):
        result = await fn("ch_lock_1")

    assert result["acquired"] is True
    assert isinstance(result["token"], str) and len(result["token"]) == 32


@pytest.mark.asyncio
async def test_acquire_lock_v2_second_call_denied():
    from workers.activities.common import acquire_channel_lock_v2

    fake_redis = _FakeRedis()
    fn = _unwrap(acquire_channel_lock_v2)
    with patch("workers.activities.common.get_redis", new=AsyncMock(return_value=fake_redis)):
        first = await fn("ch_lock_2")
        second = await fn("ch_lock_2")

    assert first["acquired"] is True
    assert second["acquired"] is False
    assert second["token"] == ""


@pytest.mark.asyncio
async def test_ten_racing_acquires_only_one_wins():
    """Simulates 10 workers racing for the same channel — only 1 should win."""
    from workers.activities.common import acquire_channel_lock_v2

    fake_redis = _FakeRedis()
    fn = _unwrap(acquire_channel_lock_v2)
    with patch("workers.activities.common.get_redis", new=AsyncMock(return_value=fake_redis)):
        results = await asyncio.gather(*[fn("ch_race") for _ in range(10)])
    winners = [r for r in results if r["acquired"]]
    assert len(winners) == 1


# ──────────────────────── checkpoint envelope ────────────────────────


class _FakeStorage:
    def __init__(self):
        self.uploaded = {}

    async def upload(self, req):
        self.uploaded[req.key] = req.data

    async def exists(self, key):
        return key in self.uploaded

    async def download(self, key):
        return self.uploaded[key]


@pytest.mark.asyncio
async def test_save_and_load_checkpoint_roundtrip():
    from workers.activities.common import load_checkpoint_data, save_checkpoint_data

    storage = _FakeStorage()

    with patch("providers.registry.ProviderRegistry.get", return_value=storage):
        await _unwrap(save_checkpoint_data)("vid_ck1", "script", {"segments": [{"id": "s1"}], "cost": 0.05})
        loaded = await _unwrap(load_checkpoint_data)("vid_ck1", "script")
    assert loaded == {"segments": [{"id": "s1"}], "cost": 0.05}


@pytest.mark.asyncio
async def test_save_checkpoint_rejects_oversized_payload():
    from workers.activities.common import save_checkpoint_data

    storage = _FakeStorage()
    with (
        patch("workers.activities.common._CHECKPOINT_MAX_BYTES", 128),
        patch("providers.registry.ProviderRegistry.get", return_value=storage),
    ):
        big = {"data": ["x" * 100 for _ in range(20)]}
        await _unwrap(save_checkpoint_data)("vid_ck2", "phase", big)
    assert storage.uploaded == {}


@pytest.mark.asyncio
async def test_load_checkpoint_rejects_corrupted_checksum():
    from workers.activities.common import load_checkpoint_data

    storage = _FakeStorage()
    envelope = {
        "v": 1,
        "content_id": "vid_ck3",
        "phase": "p",
        "sha256": "0" * 64,
        "size": 5,
        "data": {"real": "payload"},
    }
    storage.uploaded["checkpoints/vid_ck3/p.json"] = json.dumps(envelope).encode("utf-8")
    with patch("providers.registry.ProviderRegistry.get", return_value=storage):
        result = await _unwrap(load_checkpoint_data)("vid_ck3", "p")
    assert result == {}


@pytest.mark.asyncio
async def test_load_checkpoint_backcompat_legacy_bare_dict():
    from workers.activities.common import load_checkpoint_data

    storage = _FakeStorage()
    storage.uploaded["checkpoints/vid_ck4/p.json"] = json.dumps({"legacy": True}).encode("utf-8")
    with patch("providers.registry.ProviderRegistry.get", return_value=storage):
        result = await _unwrap(load_checkpoint_data)("vid_ck4", "p")
    assert result == {"legacy": True}


# ──────────────────────── notification-dispatcher backoff ────────────────────────


def test_backoff_delay_grows_exponentially():
    # Ensure the dispatcher path is importable
    disp_path = os.path.join(os.path.dirname(__file__), "..", "backend", "workers", "notification-dispatcher")
    if disp_path not in sys.path:
        sys.path.insert(0, disp_path)

    from src.dispatcher import _backoff_delay

    d1 = _backoff_delay(1)
    d2 = _backoff_delay(2)
    d3 = _backoff_delay(3)
    # Jitter is ±25% so use loose bounds
    assert 0.75 <= d1 <= 1.25
    assert 3.75 <= d2 <= 6.25
    assert 18.75 <= d3 <= 31.25


def test_backoff_delay_capped():
    disp_path = os.path.join(os.path.dirname(__file__), "..", "backend", "workers", "notification-dispatcher")
    if disp_path not in sys.path:
        sys.path.insert(0, disp_path)
    from src.dispatcher import _BACKOFF_CAP_S, _backoff_delay

    d = _backoff_delay(20)
    assert d <= _BACKOFF_CAP_S * 1.25


def test_dedup_key_stable_and_daily():
    disp_path = os.path.join(os.path.dirname(__file__), "..", "backend", "workers", "notification-dispatcher")
    if disp_path not in sys.path:
        sys.path.insert(0, disp_path)
    from src.dispatcher import _dedup_key

    a = _dedup_key("slack", "video.complete", "ch1", "v1", "2026-08-08")
    b = _dedup_key("slack", "video.complete", "ch1", "v1", "2026-08-08")
    c = _dedup_key("slack", "video.complete", "ch1", "v1", "2026-08-09")  # next day
    assert a == b
    assert a != c
    assert len(a) == 32


# ──────────────────────── sentry-agent quota ────────────────────────


@pytest.mark.asyncio
async def test_sentry_autofix_quota_blocks_after_cap(monkeypatch):
    """After N calls in a day, the quota gate must return not-allowed."""
    sa_path = os.path.join(os.path.dirname(__file__), "..", "backend", "platform", "sentry-agent")
    if sa_path not in sys.path:
        sys.path.insert(0, sa_path)

    # Minimal env for config.py import (it fails-fast on missing envs)
    for k, v in {
        "SLACK_BOT_TOKEN": "x",
        "SLACK_APP_TOKEN": "x",
        "SLACK_CRITICAL_CHANNEL_ID": "x",
        "SLACK_WARNINGS_CHANNEL_ID": "x",
        "SENTRY_AUTH_TOKEN": "x",
        "GITHUB_TOKEN": "x",
        "JIRA_EMAIL": "x",
        "JIRA_API_TOKEN": "x",
        "OPENAI_API_KEY": "x",
        "SENTRY_AUTOFIX_MAX_PER_DAY": "2",
    }.items():
        monkeypatch.setenv(k, v)

    # Force config re-import so AUTOFIX_MAX_PER_DAY reflects env
    for mod in ("config", "fix_agent"):
        if mod in sys.modules:
            del sys.modules[mod]

    fake_redis = _FakeRedis()

    class _RedisFactory:
        def __init__(self):
            self.calls = 0

        def from_url(self, *a, **kw):
            return _CountingRedis(self)

    class _CountingRedis:
        def __init__(self, parent):
            self._parent = parent

        async def incr(self, key):
            self._parent.calls += 1
            return self._parent.calls

        async def expire(self, key, ttl):
            return 1

        async def aclose(self):
            pass

    factory = _RedisFactory()
    with patch("redis.asyncio.from_url", side_effect=factory.from_url):
        from fix_agent import _check_and_bump_daily_quota

        r1 = await _check_and_bump_daily_quota()
        r2 = await _check_and_bump_daily_quota()
        r3 = await _check_and_bump_daily_quota()

    assert r1[0] is True and r1[1] == 1
    assert r2[0] is True and r2[1] == 2
    assert r3[0] is False and r3[1] == 3  # blocked by cap


# ──────────────────────── worker sizing ────────────────────────


def _import_run_production():
    """Import run_production, tolerating optional deps that aren't present locally."""
    try:
        return importlib.import_module("workers.run_production")
    except Exception:
        pytest.skip("run_production not importable in this environment")


def test_worker_sizing_caps_at_80pct_db_pool(monkeypatch):
    rp = _import_run_production()

    class _Fake:
        temporal_production_max_activities = 20
        temporal_production_max_workflow_tasks = 30
        db_pool_max_size = 10

    monkeypatch.setattr(rp, "settings", _Fake())
    max_acts, max_wf = rp._compute_worker_sizing()
    assert max_acts == 8
    assert max_wf == 30


def test_worker_sizing_respects_configured_when_below_cap(monkeypatch):
    rp = _import_run_production()

    class _Fake:
        temporal_production_max_activities = 3
        temporal_production_max_workflow_tasks = 10
        db_pool_max_size = 10

    monkeypatch.setattr(rp, "settings", _Fake())
    max_acts, _ = rp._compute_worker_sizing()
    assert max_acts == 3
