"""Unit tests for the hybrid semantic search — AE-356."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services_api.dashboard.v2.library import (
    SearchIn,
    _fts_search,
    _fuse,
    _semantic_search,
    dam_search,
)


@pytest.mark.asyncio
async def test_fts_search_uses_legacy_query(mock_pool):
    mock_pool.fetch.return_value = []
    body = SearchIn(q="penguins", scope="workspace", mode="fts")
    rows = await _fts_search(body)
    assert rows == []
    sql = mock_pool.fetch.await_args.args[0]
    assert "to_tsvector" in sql
    assert "FROM dam_assets" in sql


@pytest.mark.asyncio
async def test_semantic_search_returns_none_when_no_query(mock_pool):
    body = SearchIn(q="", scope="workspace", mode="semantic")
    assert await _semantic_search(body) is None


@pytest.mark.asyncio
async def test_semantic_search_returns_none_when_embedding_fails(mock_pool):
    from llm.embeddings import EmbeddingError

    with patch(
        "llm.embeddings.embed_text",
        AsyncMock(side_effect=EmbeddingError("down")),
    ):
        body = SearchIn(q="x", scope="workspace", mode="semantic")
        assert await _semantic_search(body) is None


@pytest.mark.asyncio
async def test_semantic_search_runs_vector_query(mock_pool):
    mock_pool.fetch.return_value = []
    with patch(
        "llm.embeddings.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    ):
        body = SearchIn(q="penguins", scope="workspace", mode="semantic")
        rows = await _semantic_search(body)
    assert rows == []
    sql = mock_pool.fetch.await_args.args[0]
    assert "dam_text_embeddings" in sql
    assert "<=>" in sql
    assert "JOIN dam_text_embeddings" in sql


def test_fuse_prefers_assets_present_in_both_lists():
    semantic = [{"id": 1}, {"id": 2}]
    lexical = [{"id": 2}, {"id": 3}]
    fused = _fuse(semantic, lexical, limit=10)
    ids = [r["id"] for r in fused]
    assert ids[0] == 2
    assert set(ids) == {1, 2, 3}


@pytest.mark.asyncio
async def test_hybrid_endpoint_falls_back_to_fts_when_semantic_unavailable(mock_pool):
    mock_pool.fetch.return_value = []
    from llm.embeddings import EmbeddingError

    with patch(
        "llm.embeddings.embed_text",
        AsyncMock(side_effect=EmbeddingError("down")),
    ):
        resp = await dam_search(SearchIn(q="x", scope="workspace", mode="hybrid"), _=None)
    assert resp["mode"] == "fts_fallback"


@pytest.mark.asyncio
async def test_hybrid_endpoint_combines_results(mock_pool):
    sem_rows = [
        {"id": 1, "display_name": "A"},
        {"id": 2, "display_name": "B"},
    ]
    lex_rows = [
        {"id": 2, "display_name": "B"},
        {"id": 3, "display_name": "C"},
    ]

    mock_pool.fetch.side_effect = [sem_rows, lex_rows]
    with patch(
        "llm.embeddings.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    ):
        resp = await dam_search(SearchIn(q="x", scope="workspace", mode="hybrid"), _=None)

    assert resp["mode"] == "hybrid"
    ids = [r["id"] for r in resp["data"]]
    assert ids[0] == 2
    assert set(ids) == {1, 2, 3}
