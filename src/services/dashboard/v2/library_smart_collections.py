"""Smart Collections resolver (AE-359 / Library Sprint).

A *manual* dam_collection lists asset ids explicitly in ``asset_ids[]``.
A *smart* collection stores a JSONB ``query`` that re-runs on every fetch
so the membership is always live. Schema-side support already exists
(``dam_collections.kind = 'smart'``, ``dam_collections.query JSONB``) but
nothing on the backend executed the query until this module.

Query shape (locked):

.. code-block:: json

    {
      "kind":                  ["image", "video"],
      "tags_any":              ["nature", "outdoor"],
      "tags_all":              ["high-quality"],
      "license":               ["creative-commons-0", "royalty-free"],
      "expires_before":        "2027-01-01",
      "ai_tags_min_confidence": {"tag": "calm", "min": 0.75},
      "semantic":              "tranquil mountain scenery"
    }

Any subset of those keys is valid. Unknown keys are ignored (forward-
compatible with future query DSL additions).

The semantic field is opt-in and uses ``src/llm/embeddings`` — if the
embedding call fails we degrade gracefully to a structural-only match so
a Library page never hangs on a transient OpenAI hiccup.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from src.db import get_pool

logger = structlog.get_logger()

_SELECT_COLS = (
    "a.id, a.scope, a.scope_id, a.kind, a.display_name, a.mime_type, a.bytes, "
    "a.thumbnail_key, a.storage_key, a.origin, a.tags, a.metadata, a.created_at"
)


def _coerce_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def _parse_query(raw: Any) -> dict:
    """Parse the stored query JSONB into a dict, defensively."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


async def _semantic_ids(query_text: str, scope: str, scope_id: str | None,
                        top_k: int) -> list[int] | None:
    """Return asset ids ranked by semantic similarity, or None on failure."""
    if not query_text:
        return None
    from src.llm.embeddings import EmbeddingConfigError, EmbeddingError, embed_text

    try:
        vector = await embed_text(query_text)
    except (EmbeddingConfigError, EmbeddingError):
        return None

    literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
    pool = await get_pool()
    args: list[Any] = [literal, scope]
    where = ["a.deleted_at IS NULL", "a.scope = $2"]
    if scope_id:
        args.append(scope_id)
        where.append(f"a.scope_id = ${len(args)}")
    args.append(top_k)
    rows = await pool.fetch(
        f"""
        SELECT a.id
          FROM dam_assets a
          JOIN dam_text_embeddings e ON e.asset_id = a.id
         WHERE {" AND ".join(where)}
         ORDER BY e.embedding <=> $1::vector
         LIMIT ${len(args)}
        """,
        *args,
    )
    return [int(r["id"]) for r in rows]


async def resolve_smart_collection(
    collection_id: int, *, limit: int = 200
) -> list[dict]:
    """Translate a smart collection's ``query`` JSONB into asset rows.

    Manual collections (``kind='manual'``) return their explicit
    ``asset_ids[]`` member list — same wire format, so the dashboard can
    treat both kinds uniformly.

    Never raises into the caller; logs and returns ``[]`` on DB errors.
    """
    pool = await get_pool()
    try:
        col = await pool.fetchrow(
            "SELECT id, kind, scope, scope_id, query, asset_ids "
            "  FROM dam_collections WHERE id = $1",
            collection_id,
        )
    except Exception as exc:
        logger.warning("smart_collection.lookup_failed",
                       collection_id=collection_id, error=str(exc))
        return []
    if col is None:
        return []

    if col["kind"] == "manual":
        asset_ids = list(col["asset_ids"] or [])
        if not asset_ids:
            return []
        rows = await pool.fetch(
            f"SELECT {_SELECT_COLS} FROM dam_assets a "
            "WHERE a.id = ANY($1::bigint[]) AND a.deleted_at IS NULL "
            "ORDER BY array_position($1::bigint[], a.id)",
            asset_ids,
        )
        return [dict(r) for r in rows]

    q = _parse_query(col["query"])
    scope = col["scope"]
    scope_id = col["scope_id"]

    where = ["a.deleted_at IS NULL", "a.scope = $1"]
    args: list[Any] = [scope]
    if scope_id:
        args.append(scope_id)
        where.append(f"a.scope_id = ${len(args)}")

    kinds = _coerce_list(q.get("kind"))
    if kinds:
        args.append(kinds)
        where.append(f"a.kind = ANY(${len(args)})")

    tags_any = _coerce_list(q.get("tags_any"))
    if tags_any:
        args.append(tags_any)
        where.append(f"a.tags && ${len(args)}::text[]")

    tags_all = _coerce_list(q.get("tags_all"))
    if tags_all:
        args.append(tags_all)
        where.append(f"a.tags @> ${len(args)}::text[]")

    licenses = _coerce_list(q.get("license"))
    if licenses:
        args.append(licenses)
        where.append(f"a.license = ANY(${len(args)})")

    expires_before = q.get("expires_before")
    if expires_before:
        args.append(str(expires_before))
        where.append(f"a.expires_at IS NOT NULL AND a.expires_at <= ${len(args)}::timestamptz")

    ai_tags_min = q.get("ai_tags_min_confidence")
    if isinstance(ai_tags_min, dict) and ai_tags_min.get("tag") is not None:
        tag = str(ai_tags_min["tag"])
        try:
            min_conf = float(ai_tags_min.get("min", 0))
        except (TypeError, ValueError):
            min_conf = 0.0
        args.append(tag)
        tag_param = f"${len(args)}"
        args.append(min_conf)
        conf_param = f"${len(args)}"
        where.append(f"COALESCE((a.ai_tags ->> {tag_param})::float, 0) >= {conf_param}")

    semantic_query = (q.get("semantic") or "").strip()
    if semantic_query:
        sem_ids = await _semantic_ids(
            semantic_query, scope, scope_id, top_k=max(limit * 3, 60)
        )
        if sem_ids is not None:
            if not sem_ids:
                return []
            args.append(sem_ids)
            where.append(f"a.id = ANY(${len(args)}::bigint[])")

    args.append(limit)
    sql = (
        f"SELECT {_SELECT_COLS} FROM dam_assets a "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY a.created_at DESC LIMIT ${len(args)}"
    )
    rows = await pool.fetch(sql, *args)
    return [dict(r) for r in rows]
