"""Unit tests for llm.embeddings — AE-508 / P0."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import llm.embeddings as emb_mod
from llm.embeddings import (
    EMBEDDING_DIM,
    EmbeddingConfigError,
    EmbeddingError,
    _assert_safe_identifier,
    _format_vector,
    embed_and_store,
    embed_text,
    semantic_search,
)


def _make_response(status: int, body: dict | str):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    if isinstance(body, dict):
        response.json = MagicMock(return_value=body)
        response.text = ""
    else:
        response.text = body
        response.json = MagicMock(side_effect=ValueError())
    return response


def _good_payload(dim: int = EMBEDDING_DIM) -> dict:
    return {
        "data": [{"embedding": [0.001] * dim}],
        "usage": {"prompt_tokens": 12},
    }




def test_format_vector_emits_pgvector_literal():
    assert _format_vector([0.1, 0.2]) == "[0.100000,0.200000]"


def test_safe_identifier_rejects_quotes_and_spaces():
    _assert_safe_identifier("brain_decisions")
    with pytest.raises(ValueError):
        _assert_safe_identifier("brain decisions")
    with pytest.raises(ValueError):
        _assert_safe_identifier("brain; DROP TABLE")
    with pytest.raises(ValueError):
        _assert_safe_identifier("")




@pytest.mark.asyncio
async def test_embed_text_returns_vector_and_records_cost(mock_pool):
    captured = []

    async def fake_post(url, headers, json):
        captured.append({"url": url, "json": json})
        class _R:
            status_code = 200
            text = ""
            def json(self):
                return _good_payload()
        return _R()

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers, json):
            return await fake_post(url, headers, json)

    with patch("llm.embeddings.settings.openai_api_key", "sk-test"), \
         patch("llm.embeddings.httpx.AsyncClient", _Client):
        vec = await embed_text("hello world")

    assert len(vec) == EMBEDDING_DIM
    mock_pool.execute.assert_awaited()


@pytest.mark.asyncio
async def test_embed_text_raises_config_error_without_api_key():
    with patch("llm.embeddings.settings.openai_api_key", ""):
        with pytest.raises(EmbeddingConfigError):
            await embed_text("x")


@pytest.mark.asyncio
async def test_embed_text_retries_on_5xx_then_succeeds(mock_pool):
    attempts = {"n": 0}

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers, json):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return _make_response(503, "boom")
            return _make_response(200, _good_payload())

    with patch("llm.embeddings.settings.openai_api_key", "sk-test"), \
         patch("llm.embeddings.httpx.AsyncClient", _Client), \
         patch("llm.embeddings.asyncio.sleep", AsyncMock()):
        vec = await embed_text("retry me")

    assert len(vec) == EMBEDDING_DIM
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_embed_text_does_not_retry_on_4xx(mock_pool):
    attempts = {"n": 0}

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers, json):
            attempts["n"] += 1
            return _make_response(400, "bad request")

    with patch("llm.embeddings.settings.openai_api_key", "sk-test"), \
         patch("llm.embeddings.httpx.AsyncClient", _Client), \
         patch("llm.embeddings.asyncio.sleep", AsyncMock()):
        with pytest.raises(EmbeddingError):
            await embed_text("permanent fail")

    assert attempts["n"] == 1




@pytest.mark.asyncio
async def test_embed_and_store_updates_target_row(mock_pool):
    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers, json):
            return _make_response(200, _good_payload())

    with patch("llm.embeddings.settings.openai_api_key", "sk-test"), \
         patch("llm.embeddings.httpx.AsyncClient", _Client):
        await embed_and_store(
            "log this decision",
            table="brain_decisions",
            row_id=42,
            column="embedding",
        )

    update_calls = [c for c in mock_pool.execute.await_args_list
                    if "UPDATE" in (c.args[0] if c.args else "")]
    assert update_calls, "expected at least one UPDATE call"
    last = update_calls[-1]
    assert "brain_decisions" in last.args[0]
    assert last.args[2] == 42
    assert last.args[1].startswith("[")


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_on_embedding_failure(mock_pool):
    """Failures in OpenAI must NOT propagate — return [] for resilience."""
    with patch("llm.embeddings.embed_text", AsyncMock(side_effect=EmbeddingError("down"))):
        rows = await semantic_search("query", table="brain_decisions")
    assert rows == []


@pytest.mark.asyncio
async def test_semantic_search_calls_db_with_vector_param(mock_pool):
    mock_pool.fetch.return_value = []

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers, json):
            return _make_response(200, _good_payload())

    with patch("llm.embeddings.settings.openai_api_key", "sk-test"), \
         patch("llm.embeddings.httpx.AsyncClient", _Client), \
         patch("llm.embeddings.get_flag", AsyncMock(return_value=False)):
        rows = await semantic_search("hello", table="brain_decisions", top_k=5)

    assert rows == []
    mock_pool.fetch.assert_awaited()
    sql, *params = mock_pool.fetch.await_args.args
    assert "FROM brain_decisions" in sql
    assert "LIMIT 5" in sql
    assert params[0].startswith("[")
