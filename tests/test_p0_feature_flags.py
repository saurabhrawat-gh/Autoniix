"""Unit tests for src.flags — AE-510 / P0."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import src.flags as flags_mod
from src.flags import clear_cache, get_flag, invalidate_cache


@pytest.fixture(autouse=True)
def _clear_flag_cache():
    """Each test starts with an empty cache."""
    clear_cache()
    yield
    clear_cache()


@pytest.mark.asyncio
async def test_get_flag_returns_boolean_from_enabled_column(mock_pool):
    mock_pool.fetchrow.return_value = {"enabled": True, "payload": {}}
    assert await get_flag("brain.advisory_mode") is True


@pytest.mark.asyncio
async def test_get_flag_returns_payload_value_when_present(mock_pool):
    mock_pool.fetchrow.return_value = {"enabled": True, "payload": {"value": 30}}
    assert await get_flag("temporal.signal_check_interval_seconds") == 30


@pytest.mark.asyncio
async def test_get_flag_uses_default_when_row_missing(mock_pool):
    mock_pool.fetchrow.return_value = None
    assert await get_flag("nonexistent.flag", default="fallback") == "fallback"


@pytest.mark.asyncio
async def test_get_flag_uses_default_on_db_error():
    """A DB failure must NEVER raise into business code."""
    async def _boom():
        raise RuntimeError("db down")
    with patch.object(flags_mod, "get_pool", side_effect=_boom):
        assert await get_flag("any.key", default="safe") == "safe"


@pytest.mark.asyncio
async def test_get_flag_caches_value_within_ttl(mock_pool):
    mock_pool.fetchrow.return_value = {"enabled": True, "payload": {}}
    await get_flag("x.flag")
    await get_flag("x.flag")
    await get_flag("x.flag")
    # Only one DB hit despite three reads — cache is working.
    assert mock_pool.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_invalidate_cache_forces_db_reread(mock_pool):
    mock_pool.fetchrow.return_value = {"enabled": True, "payload": {}}
    await get_flag("x.flag")
    invalidate_cache("x.flag")
    await get_flag("x.flag")
    assert mock_pool.fetchrow.await_count == 2
