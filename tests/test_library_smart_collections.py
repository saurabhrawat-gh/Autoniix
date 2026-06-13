"""Unit tests for Smart Collections resolver — AE-359."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.services.dashboard.v2.library_smart_collections import (
    _coerce_list,
    _parse_query,
    resolve_smart_collection,
)


def test_coerce_list_handles_str_list_and_none():
    assert _coerce_list(None) == []
    assert _coerce_list("x") == ["x"]
    assert _coerce_list(["a", "b"]) == ["a", "b"]
    assert _coerce_list([]) == []


def test_parse_query_accepts_dict_and_json_string():
    assert _parse_query({"kind": ["image"]}) == {"kind": ["image"]}
    assert _parse_query('{"kind": ["video"]}') == {"kind": ["video"]}
    assert _parse_query(None) == {}
    assert _parse_query("not json") == {}


@pytest.mark.asyncio
async def test_resolve_returns_empty_when_collection_missing(mock_pool):
    mock_pool.fetchrow.return_value = None
    assert await resolve_smart_collection(999) == []


@pytest.mark.asyncio
async def test_resolve_returns_manual_member_list(mock_pool):
    mock_pool.fetchrow.return_value = {
        "id": 1, "kind": "manual", "scope": "workspace", "scope_id": None,
        "query": {}, "asset_ids": [10, 11, 12],
    }
    mock_pool.fetch.return_value = [
        {"id": 10}, {"id": 11}, {"id": 12},
    ]
    rows = await resolve_smart_collection(1)
    assert len(rows) == 3
    # Manual path uses ANY($1) preserving order via array_position
    sql = mock_pool.fetch.await_args.args[0]
    assert "array_position" in sql


@pytest.mark.asyncio
async def test_resolve_smart_translates_query_to_sql(mock_pool):
    mock_pool.fetchrow.return_value = {
        "id": 2, "kind": "smart", "scope": "workspace", "scope_id": "WS_1",
        "query": json.dumps({
            "kind":     ["image", "video"],
            "tags_any": ["nature"],
            "tags_all": ["hq"],
            "license":  ["creative-commons-0"],
            "expires_before": "2027-01-01",
            "ai_tags_min_confidence": {"tag": "calm", "min": 0.7},
        }),
        "asset_ids": [],
    }
    mock_pool.fetch.return_value = []
    await resolve_smart_collection(2)
    sql = mock_pool.fetch.await_args.args[0]
    # Every clause from the query JSONB lands in the SQL.
    assert "a.kind = ANY" in sql
    assert "a.tags && " in sql
    assert "a.tags @> " in sql
    assert "a.license = ANY" in sql
    assert "a.expires_at" in sql
    assert "ai_tags ->>" in sql


@pytest.mark.asyncio
async def test_resolve_smart_short_circuits_when_semantic_returns_empty(mock_pool):
    """If semantic search returns no candidates, the resolver must NOT run
    a SQL query that would return everything — it returns []."""
    mock_pool.fetchrow.return_value = {
        "id": 3, "kind": "smart", "scope": "workspace", "scope_id": None,
        "query": json.dumps({"semantic": "mountain dawn"}),
        "asset_ids": [],
    }
    with patch(
        "src.services.dashboard.v2.library_smart_collections._semantic_ids",
        AsyncMock(return_value=[]),
    ):
        rows = await resolve_smart_collection(3)
    assert rows == []


@pytest.mark.asyncio
async def test_resolve_smart_degrades_when_semantic_unavailable(mock_pool):
    """When _semantic_ids returns None (e.g. OpenAI down), the resolver
    should still produce structural matches — it does not include the
    semantic candidate intersection."""
    mock_pool.fetchrow.return_value = {
        "id": 4, "kind": "smart", "scope": "workspace", "scope_id": None,
        "query": json.dumps({"semantic": "...", "kind": ["image"]}),
        "asset_ids": [],
    }
    mock_pool.fetch.return_value = []
    with patch(
        "src.services.dashboard.v2.library_smart_collections._semantic_ids",
        AsyncMock(return_value=None),
    ):
        await resolve_smart_collection(4)
    sql = mock_pool.fetch.await_args.args[0]
    # Structural filter is present, semantic id list is NOT.
    assert "a.kind = ANY" in sql
    assert "a.id = ANY" not in sql
