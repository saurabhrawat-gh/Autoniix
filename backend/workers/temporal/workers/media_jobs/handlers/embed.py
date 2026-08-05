"""``embed`` handler — compute a text embedding for an asset.

Uses the centralised P0 embedding helper (``src/llm/embeddings.py``) and
stores the result in ``dam_text_embeddings`` (vector(1536)). The text used
for the embedding is a composition of display_name + tags + ai_tags +
any caption-like metadata, so future LLM-driven semantic search across
the DAM can hit this single column.

Images / videos / audio that do not have a textual description fall back
to display_name + tag list, which is still useful for free-text search.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from llm.embeddings import EmbeddingConfigError, EmbeddingError, embed_text

logger = structlog.get_logger()

KIND = "embed"


def _build_text(asset: dict) -> str:
    """Concatenate the textual signals available for the asset.

    Order matters — the most discriminative tokens first so the embedding
    biases towards them when text gets truncated by the API tokenizer.
    """
    parts: list[str] = []
    if asset.get("display_name"):
        parts.append(str(asset["display_name"]))
    tags = asset.get("tags") or []
    if isinstance(tags, list) and tags:
        parts.append("tags: " + ", ".join(str(t) for t in tags))
    ai_tags = asset.get("ai_tags") or {}
    if isinstance(ai_tags, str):
        try:
            ai_tags = json.loads(ai_tags)
        except Exception:
            ai_tags = {}
    if isinstance(ai_tags, dict) and ai_tags:
        parts.append("ai_tags: " + ", ".join(sorted(ai_tags.keys())))
    metadata = asset.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if isinstance(metadata, dict):
        caption = metadata.get("caption") or metadata.get("description")
        if caption:
            parts.append(str(caption))
    return "\n".join(parts).strip()


async def run(pool: Any, asset: dict, job: dict) -> dict:
    text = _build_text(asset)
    if not text:
        return {
            "status": "skipped",
            "reason": "no text signal available (empty display_name + no tags)",
        }

    try:
        vector = await embed_text(text)
    except EmbeddingConfigError as exc:
        return {"status": "skipped", "reason": f"embedding disabled: {exc!s}"}
    except EmbeddingError as exc:
        return {"status": "failed", "reason": f"openai embed failed: {exc!s}"}

    literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
    await pool.execute(
        """
        INSERT INTO dam_text_embeddings (asset_id, embedding, source_text, model, updated_at)
        VALUES ($1, $2::vector, $3, $4, NOW())
        ON CONFLICT (asset_id) DO UPDATE
            SET embedding = EXCLUDED.embedding,
                source_text = EXCLUDED.source_text,
                model = EXCLUDED.model,
                updated_at = NOW()
        """,
        asset["id"],
        literal,
        text[:8000],
        "text-embedding-3-small",
    )
    return {"status": "done", "result": {"dim": len(vector), "chars": len(text)}}
