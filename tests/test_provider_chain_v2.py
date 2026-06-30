"""Unit tests for the scope + content-mode aware provider chain resolver.

These tests focus on the *resolution logic* in `src/providers/chain.py`:
the SQL is stubbed (via a fake asyncpg connection) and we assert that the
right (scope, scope_id, content_mode) tuples are queried in the right
order, and that the merge keeps the first occurrence of each credential
while always appending the default-fallback row last.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.providers import chain as chain_mod


class _FakeConn:
    """Records every call to ``fetch`` / ``fetchrow`` and returns canned data."""

    def __init__(self, layer_rows: dict[tuple, list[dict]], default_fallback: dict | None):
        self._layer_rows = layer_rows
        self._default_fallback = default_fallback
        self.fetch_calls: list[tuple] = []
        self.fetchrow_calls: list[tuple] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict]:
        if "FROM provider_chains_v2" in sql:
            scope, category, sid, mode = args[0], args[1], args[2], args[3]
            key = (scope, sid, mode, category)
            self.fetch_calls.append(key)
            return list(self._layer_rows.get(key, []))
        return []

    async def fetchrow(self, sql: str, *args: Any) -> dict | None:
        self.fetchrow_calls.append(args)
        return self._default_fallback


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):  # type: ignore[override]
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                return pool._conn

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.fixture(autouse=True)
def _clear_caches():
    chain_mod._chain_cache.clear()
    yield
    chain_mod._chain_cache.clear()


def _row(cid: int, name: str = "openai", model: str | None = None) -> dict:
    return {
        "id": cid,
        "provider_name": name,
        "vault_path": f"providers/llm.script/{name}",
        "extra_config": None,
        "model": model,
        "enabled": True,
        "last_health_ok": True,
        "label": f"cred-{cid}",
        "position": 0,
        "fallback_strategy": "on_error",
    }


@pytest.mark.asyncio
async def test_resolution_order_is_most_specific_first():
    """Channel+mode rows must precede channel rows must precede workspace+mode rows…"""
    layers = {
        ("channel",   "CH1", "short", "llm.script"): [_row(1)],
        ("channel",   "CH1", None,    "llm.script"): [_row(2)],
        ("workspace", None,  "short", "llm.script"): [_row(3)],
        ("workspace", None,  None,    "llm.script"): [_row(4)],
        ("system",    None,  None,    "llm.script"): [_row(5)],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        rows = await chain_mod._load_chain(
            "llm.script", channel_id="CH1", content_mode="short",
        )

    ids = [r["id"] for r in rows]
    assert ids == [1, 2, 3, 4, 5], f"unexpected order: {ids}"

    origins = [r["__origin__"] for r in rows]
    assert origins == ["channel+mode", "channel", "workspace+mode", "workspace", "system"]


@pytest.mark.asyncio
async def test_partial_channel_override_inherits_workspace_tail():
    """A channel override with one extra row still inherits the workspace chain."""
    layers = {
        ("channel",   "CH1", None, "llm.script"): [_row(10)],
        ("workspace", None,  None, "llm.script"): [_row(20), _row(30)],
        ("system",    None,  None, "llm.script"): [],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        rows = await chain_mod._load_chain(
            "llm.script", channel_id="CH1", content_mode=None,
        )
    assert [r["id"] for r in rows] == [10, 20, 30]


@pytest.mark.asyncio
async def test_dedup_keeps_first_occurrence():
    """If the same credential appears in two layers, only the higher-priority
    occurrence is kept (with its origin label)."""
    shared = _row(7, model="gpt-4o")
    layers = {
        ("channel",   "CH1", None, "llm.script"): [shared],
        ("workspace", None,  None, "llm.script"): [shared, _row(8)],
        ("system",    None,  None, "llm.script"): [],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        rows = await chain_mod._load_chain(
            "llm.script", channel_id="CH1", content_mode=None,
        )
    assert [r["id"] for r in rows] == [7, 8]
    assert rows[0]["__origin__"] == "channel"


@pytest.mark.asyncio
async def test_default_fallback_always_appended_last():
    layers = {
        ("workspace", None, None, "llm.script"): [_row(1)],
        ("system",    None, None, "llm.script"): [],
    }
    fb = {
        "id": 99, "provider_name": "openai",
        "vault_path": "providers/llm.script/openai",
        "extra_config": None, "model": "gpt-4o-mini",
        "enabled": True, "last_health_ok": True, "label": "house-key",
    }
    conn = _FakeConn(layers, default_fallback=fb)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        rows = await chain_mod._load_chain(
            "llm.script", channel_id=None, content_mode=None,
        )
    assert [r["id"] for r in rows] == [1, 99]
    assert rows[-1]["__origin__"] == "default"


@pytest.mark.asyncio
async def test_mode_specific_only_queried_when_mode_given():
    """When no content_mode is passed, the +mode layers must not be queried."""
    layers = {
        ("workspace", None, None, "llm.script"): [_row(1)],
        ("system",    None, None, "llm.script"): [],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        await chain_mod._load_chain(
            "llm.script", channel_id=None, content_mode=None,
        )
    scopes_queried = [c[0] for c in conn.fetch_calls]
    assert scopes_queried == ["workspace", "system"]




@pytest.mark.asyncio
async def test_disabled_credential_skipped_by_layer_loader():
    """`_load_layer` SQL filters `pc.enabled = TRUE` — when the fake layer
    returns no rows for a disabled cred, the merged chain should be empty."""
    layers: dict[tuple, list[dict]] = {
        ("workspace", None, None, "llm.script"): [],
        ("system",    None, None, "llm.script"): [],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))):
        rows = await chain_mod._load_chain(
            "llm.script", channel_id=None, content_mode=None,
        )
    assert rows == []


@pytest.mark.asyncio
async def test_resolve_chain_returns_empty_sentinel_when_no_rows():
    """When the DB query succeeds but yields zero rows, resolve_chain must
    return the EMPTY_CHAIN sentinel (not None) so the registry can raise
    NoProviderConfigured instead of falling back to env vars."""
    layers: dict[tuple, list[dict]] = {
        ("workspace", None, None, "llm.script"): [],
        ("system",    None, None, "llm.script"): [],
    }
    conn = _FakeConn(layers, default_fallback=None)
    with patch("src.db.get_pool", new=AsyncMock(return_value=_FakePool(conn))), \
         patch.object(chain_mod, "_flag_enabled", new=AsyncMock(return_value=True)):
        result = await chain_mod.resolve_chain("llm.script", registry_map={})
    assert result is chain_mod.EMPTY_CHAIN


def test_no_provider_configured_message_includes_hint():
    exc = chain_mod.NoProviderConfigured(
        "llm.script", channel_id="CH1", content_mode="short",
    )
    msg = str(exc)
    assert "llm.script" in msg
    assert "channel=CH1" in msg
    assert "mode=short" in msg
    assert "/dashboard/providers" in msg



def test_invalidate_wildcard_clears_everything():
    chain_mod._chain_cache[("CH1", "short", "llm.script")] = ("x", 9e9)
    chain_mod._chain_cache[("",   "",      "image.thumbnail")] = ("y", 9e9)
    chain_mod.invalidate()
    assert chain_mod._chain_cache == {}


def test_invalidate_by_category_only_drops_matching():
    chain_mod._chain_cache[("CH1", "short", "llm.script")] = ("a", 9e9)
    chain_mod._chain_cache[("CH1", "short", "image.thumbnail")] = ("b", 9e9)
    chain_mod._chain_cache[("",   "",      "llm.script")] = ("c", 9e9)
    chain_mod.invalidate(category="llm.script")
    assert set(chain_mod._chain_cache.keys()) == {("CH1", "short", "image.thumbnail")}


def test_invalidate_by_channel_only_drops_matching():
    chain_mod._chain_cache[("CH1", "short", "llm.script")] = ("a", 9e9)
    chain_mod._chain_cache[("CH2", "short", "llm.script")] = ("b", 9e9)
    chain_mod._chain_cache[("",   "",      "llm.script")] = ("c", 9e9)
    chain_mod.invalidate(channel_id="CH1")
    assert ("CH1", "short", "llm.script") not in chain_mod._chain_cache
    assert ("CH2", "short", "llm.script") in chain_mod._chain_cache
    assert ("", "", "llm.script") in chain_mod._chain_cache
