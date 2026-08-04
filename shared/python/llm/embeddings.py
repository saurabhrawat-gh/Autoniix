"""Centralised OpenAI embedding + pgvector semantic-search helper.

Until now, embedding work has been done in two unrelated ways across the
codebase:

* **Local CPU embeddings** (``src/services/research/similarity.py`` and
  ``competitor_insights.py``) compute 384-dim ``all-MiniLM-L6-v2`` vectors.
  Cheap, zero API spend, but lower fidelity. Owned by the research service.
* **No central API embedding helper exists.** Every later agentic service
  (Brain, Preventor, Compliance, …) needs higher-fidelity embeddings against
  ``brain_decisions`` and other agentic tables, and we don't want each
  service to roll its own OpenAI client.

This module is the single home for the API-backed embedding path, using
``text-embedding-3-small`` ($0.02 / 1M tokens, 1536-dim). It exposes a
small, deliberate surface:

* :func:`embed_text(text)` → ``list[float]`` (length 1536)
* :func:`embed_and_store(text, table=..., row_id=..., column=...)` →
  compute + UPDATE in one round-trip
* :func:`semantic_search(query, table=..., top_k=...)` → ranked rows

The helper:

* records cost into ``api_usage`` so the daily-cost rollup the LLM router
  already exposes is the same dollar source-of-truth across LLM + embedding
  spend;
* retries 429 / 5xx with exponential backoff up to 3 attempts;
* applies relevance-decay scoring when
  ``rag.relevance_decay.enabled`` is TRUE and the target table has a
  ``rag_index_metadata`` row.

Existing local-CPU embeddings in ``research/similarity.py`` are **not**
touched by this ticket — refactoring those is a separate cost / fidelity
decision belonging to a later ticket.

This module is part of AE-508 / P0 — Agentic Foundation.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx
import structlog

from core.config import settings
from core.db import get_pool
from core.flags import get_flag

logger = structlog.get_logger()

OPENAI_BASE_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

PRICING_PER_TOKEN: dict[str, float] = {
    "text-embedding-3-small": 0.02 / 1_000_000,
    "text-embedding-3-large": 0.13 / 1_000_000,
}

_HTTP_TIMEOUT_S = 30.0
_MAX_ATTEMPTS = 3
_RETRY_INITIAL_DELAY_S = 0.5
_RETRY_MAX_DELAY_S = 8.0




class EmbeddingError(RuntimeError):
    """Raised when the OpenAI embedding API fails after all retries."""


class EmbeddingConfigError(RuntimeError):
    """Raised when the OpenAI API key is not configured."""




def _format_vector(values: list[float]) -> str:
    """pgvector accepts ``'[v1,v2,…]'`` strings for ``vector(N)`` columns."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def _is_transient(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


async def _post_with_retry(payload: dict) -> dict:
    """POST to the embeddings endpoint with exponential-backoff retry.

    Permanent failures (4xx other than 429) raise immediately. Transient
    failures (429, 5xx, network errors) retry up to ``_MAX_ATTEMPTS``. The
    final failure raises :class:`EmbeddingError`.
    """
    if not settings.openai_api_key:
        raise EmbeddingConfigError(
            "OPENAI_API_KEY not set; the embedding helper requires it."
        )
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    last_error: str | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
                response = await client.post(
                    OPENAI_BASE_URL, headers=headers, json=payload
                )
            if response.status_code == 200:
                return response.json()
            if not _is_transient(response.status_code):
                raise EmbeddingError(
                    f"openai embeddings {response.status_code}: {response.text[:300]}"
                )
            last_error = f"{response.status_code}: {response.text[:200]}"
        except httpx.RequestError as exc:
            last_error = f"network: {exc!s}"
        if attempt < _MAX_ATTEMPTS:
            delay = min(
                _RETRY_INITIAL_DELAY_S * (2 ** (attempt - 1)),
                _RETRY_MAX_DELAY_S,
            )
            delay = random.uniform(0.0, delay)
            await asyncio.sleep(delay)
    raise EmbeddingError(
        f"openai embeddings failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    )


async def _record_cost(
    *,
    model: str,
    tokens_in: int,
    cost_usd: float,
    latency_ms: int,
    content_id: str | None,
    channel_id: str | None,
) -> None:
    """Mirror the LLM router's ``api_usage`` write so daily cost rollup works."""
    try:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO api_usage
                (content_id, channel_id, service, provider, model,
                 tokens_in, cost_usd, latency_ms, success)
            VALUES ($1, $2, 'embedding', 'openai', $3, $4, $5, $6, TRUE)
            """,
            content_id,
            channel_id,
            model,
            tokens_in,
            cost_usd,
            latency_ms,
        )
    except Exception as exc:
        logger.warning("embeddings.cost_record_failed", error=str(exc))




async def embed_text(
    text: str,
    *,
    model: str = DEFAULT_MODEL,
    content_id: str | None = None,
    channel_id: str | None = None,
) -> list[float]:
    """Return an embedding vector for ``text``.

    Raises :class:`EmbeddingError` on persistent failure (after retries).
    Records cost in ``api_usage`` so it shows up in the per-channel rollup.

    ``content_id`` / ``channel_id`` are optional but recommended — they let
    cost-attribution land against the right row, matching the LLM router.
    """
    if not text:
        raise ValueError("embed_text: empty text")

    start = time.monotonic()
    data = await _post_with_retry({"model": model, "input": text})
    latency_ms = int((time.monotonic() - start) * 1000)

    try:
        vector = data["data"][0]["embedding"]
        tokens_in = int(data.get("usage", {}).get("prompt_tokens", 0))
    except (KeyError, IndexError) as exc:
        raise EmbeddingError(f"unexpected embeddings response shape: {exc!s}")

    if len(vector) != EMBEDDING_DIM and model == DEFAULT_MODEL:
        raise EmbeddingError(
            f"expected {EMBEDDING_DIM}-d vector, got {len(vector)}"
        )

    cost_usd = tokens_in * PRICING_PER_TOKEN.get(model, 0.0)
    await _record_cost(
        model=model,
        tokens_in=tokens_in,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        content_id=content_id,
        channel_id=channel_id,
    )
    return vector


async def embed_and_store(
    text: str,
    *,
    table: str,
    row_id: int | str,
    column: str = "embedding",
    id_column: str = "id",
    model: str = DEFAULT_MODEL,
    content_id: str | None = None,
    channel_id: str | None = None,
) -> None:
    """Compute an embedding for ``text`` and UPDATE the target row.

    The caller is responsible for choosing the correct ``table`` /
    ``column`` and ensuring the column is a pgvector of matching
    dimensionality. ``id_column`` defaults to ``id`` (matches our
    convention for ``brain_decisions``).
    """
    _assert_safe_identifier(table)
    _assert_safe_identifier(column)
    _assert_safe_identifier(id_column)

    vector = await embed_text(
        text, model=model, content_id=content_id, channel_id=channel_id
    )
    pool = await get_pool()
    await pool.execute(
        f"UPDATE {table} SET {column} = $1::vector WHERE {id_column} = $2",
        _format_vector(vector),
        row_id,
    )


async def semantic_search(
    query: str,
    *,
    table: str,
    top_k: int = 10,
    column: str = "embedding",
    id_column: str = "id",
    select_columns: str = "*",
    where: str | None = None,
    where_params: tuple | None = None,
    model: str = DEFAULT_MODEL,
    relevance_decay_days: int | None = None,
    content_id: str | None = None,
    channel_id: str | None = None,
) -> list[dict]:
    """pgvector cosine-similarity search over ``table.column``.

    Returns rows sorted by descending similarity. Each row includes the
    base columns from ``select_columns`` plus:

    * ``cosine_sim`` — raw similarity in [0, 1]
    * ``score`` — equal to ``cosine_sim`` unless time-decay is applied

    Time-decay is applied iff ALL of:
      * the ``rag.relevance_decay.enabled`` flag is TRUE, AND
      * either ``relevance_decay_days`` is provided as a kwarg, OR the
        target table has a ``rag_index_metadata`` row.

    ``where`` is appended verbatim — call-sites are trusted services. Use
    ``where_params`` for any user-derived values.

    On embedding failure this helper returns ``[]`` rather than raising so
    a hiccup in OpenAI never crashes a caller. The failure is logged.
    """
    _assert_safe_identifier(table)
    _assert_safe_identifier(column)
    _assert_safe_identifier(id_column)

    try:
        vector = await embed_text(
            query, model=model, content_id=content_id, channel_id=channel_id
        )
    except (EmbeddingError, EmbeddingConfigError) as exc:
        logger.warning("semantic_search.embed_failed", table=table, error=str(exc))
        return []

    vector_literal = _format_vector(vector)
    decay_days = await _resolve_decay_days(table, relevance_decay_days)

    base_select = (
        f"SELECT {select_columns}, "
        f"1 - ({column} <=> $1::vector) AS cosine_sim "
    )
    if decay_days is not None:
        base_select += (
            f", (1 - ({column} <=> $1::vector)) * "
            f"exp(- GREATEST(EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0, 0) "
            f"/ {decay_days}.0) AS score "
        )
        order_clause = " ORDER BY score DESC"
    else:
        base_select += f", 1 - ({column} <=> $1::vector) AS score "
        order_clause = f" ORDER BY {column} <=> $1::vector"

    sql = base_select + f"FROM {table} "
    params: list[Any] = [vector_literal]
    if where:
        sql += f"WHERE {where} "
        if where_params:
            params.extend(where_params)
    sql += order_clause + f" LIMIT {int(top_k)}"

    pool = await get_pool()
    rows = await pool.fetch(sql, *params)
    return [dict(r) for r in rows]


async def _resolve_decay_days(table: str, override: int | None) -> int | None:
    """Return the relevance decay window in days, or None if disabled."""
    enabled = await get_flag("rag.relevance_decay.enabled", default=False)
    if not enabled:
        return None
    if override is not None:
        return int(override)
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT relevance_decay_days FROM rag_index_metadata WHERE table_name = $1",
            table,
        )
    except Exception as exc:
        logger.warning("semantic_search.decay_lookup_failed", table=table, error=str(exc))
        return None
    return int(row["relevance_decay_days"]) if row else None


def _assert_safe_identifier(name: str) -> None:
    """Allow only lowercase letters, digits, and underscores in identifiers.

    Defence-in-depth: identifiers are supposed to be hard-coded strings
    from trusted services, but this guard prevents a buggy refactor or a
    misrouted user value from constructing arbitrary SQL.
    """
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
