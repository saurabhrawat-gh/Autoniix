"""Similarity & Freshness — SBERT embeddings + SimHash + pgvector.

Detects near-duplicate topics across channels and measures freshness.
Uses sentence-transformers (all-MiniLM-L6-v2, 384-dim) for embeddings
and a 64-bit SimHash for fast near-duplicate screening.
Zero API cost — everything runs locally on CPU.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

import structlog

from core.db import get_pool

logger = structlog.get_logger()

_model = None
_model_lock = asyncio.Lock()
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


async def _get_model():
    """Lazy-load sentence transformer model (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model

        def _load():
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer(MODEL_NAME)

        _model = await asyncio.to_thread(_load)
        logger.info("similarity.model_loaded", model=MODEL_NAME)
        return _model


async def compute_embedding(text: str) -> list[float]:
    """Compute a 384-dim embedding for a text string."""
    model = await _get_model()
    emb = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
    return emb.tolist()


async def compute_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch compute embeddings."""
    model = await _get_model()
    embs = await asyncio.to_thread(model.encode, texts, normalize_embeddings=True, batch_size=32)
    return [e.tolist() for e in embs]


def _simhash(text: str, hashbits: int = 64) -> int:
    """Compute a 64-bit SimHash for near-duplicate detection.

    SimHash is locality-sensitive: similar texts produce similar hashes.
    Hamming distance < 12 bits → likely near-duplicate.
    """
    tokens = text.lower().split()
    v = [0] * hashbits

    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= 1 << i

    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute Hamming distance between two SimHash values."""
    return bin(hash1 ^ hash2).count("1")


async def store_topic_embedding(
    content_id: str,
    channel_id: str,
    text_type: str,
    text: str,
) -> dict:
    """
    Store an embedding + simhash for a topic/title/hook.

    Uses INSERT ... ON CONFLICT to prevent duplicate embeddings for the same
    content_id + text_type combination. If a duplicate exists, updates the
    embedding and simhash with the new values.
    """
    embedding = await compute_embedding(text)
    sh = _simhash(text)

    pool = await get_pool()
    emb_str = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"

    await pool.execute(
        """
        INSERT INTO topic_embeddings (content_id, channel_id, text_type, text_content, embedding, simhash)
        VALUES ($1, $2, $3, $4, $5::vector, $6)
        ON CONFLICT (content_id, text_type)
        DO UPDATE SET
            text_content = EXCLUDED.text_content,
            embedding = EXCLUDED.embedding,
            simhash = EXCLUDED.simhash,
            updated_at = NOW()
    """,
        content_id,
        channel_id,
        text_type,
        text,
        emb_str,
        sh,
    )

    return {"embedding_dim": len(embedding), "simhash": sh}


async def check_similarity(
    text: str,
    channel_id: str | None = None,
    text_type: str = "topic",
    top_k: int = 5,
    similarity_threshold: float = 0.35,
    simhash_threshold: int = 12,
) -> dict:
    """Check if a text is too similar to existing topics.

    Args:
        text: The candidate topic/title/hook.
        channel_id: Optional — if None, checks across ALL channels.
        text_type: Filter by type (topic, title, hook).
        top_k: Number of nearest neighbors to return.
        similarity_threshold: Cosine similarity above this = too similar (0–1 scale, where 1=identical).
        simhash_threshold: Hamming distance below this = near-duplicate.

    Returns:
        dict with: is_duplicate, max_similarity, nearest_matches[], simhash_matches[],
                   novelty_score (0–1, higher = more novel).
    """
    embedding = await compute_embedding(text)
    sh = _simhash(text)
    emb_str = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"

    pool = await get_pool()

    if channel_id:
        rows = await pool.fetch(
            """
            SELECT content_id, channel_id, text_content, simhash,
                   1 - (embedding <=> $1::vector) AS cosine_sim
            FROM topic_embeddings
            WHERE text_type = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """,
            emb_str,
            text_type,
            top_k,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT content_id, channel_id, text_content, simhash,
                   1 - (embedding <=> $1::vector) AS cosine_sim
            FROM topic_embeddings
            WHERE text_type = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """,
            emb_str,
            text_type,
            top_k,
        )

    nearest = []
    max_sim = 0.0
    simhash_matches = []

    for row in rows:
        sim = float(row["cosine_sim"])
        max_sim = max(max_sim, sim)
        nearest.append(
            {
                "content_id": row["content_id"],
                "channel_id": row["channel_id"],
                "text": row["text_content"][:100],
                "cosine_similarity": round(sim, 4),
            }
        )

        if row["simhash"]:
            hd = hamming_distance(sh, row["simhash"])
            if hd < simhash_threshold:
                simhash_matches.append(
                    {
                        "content_id": row["content_id"],
                        "text": row["text_content"][:100],
                        "hamming_distance": hd,
                    }
                )

    is_duplicate = max_sim > similarity_threshold or len(simhash_matches) > 0
    novelty_score = round(max(0, 1.0 - max_sim), 4)

    result = {
        "is_duplicate": is_duplicate,
        "max_similarity": round(max_sim, 4),
        "novelty_score": novelty_score,
        "nearest_matches": nearest,
        "simhash_matches": simhash_matches,
        "candidate_simhash": sh,
    }

    logger.info(
        "similarity.check", is_dup=is_duplicate, max_sim=round(max_sim, 3), novelty=novelty_score, matches=len(nearest)
    )

    return result


async def compute_freshness(
    topic: str,
    niche: str,
    trend_momentum: float = 0.0,
) -> dict:
    """Compute a freshness score for a topic based on:
    1. Recency of similar content in our catalog.
    2. Trend momentum (from trend_collector).
    3. Competitor coverage recency.

    Returns: dict with freshness_score (0–1), components.
    """
    pool = await get_pool()

    embedding = await compute_embedding(topic)
    emb_str = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"

    row = await pool.fetchrow(
        """
        SELECT MIN(1 - (embedding <=> $1::vector)) AS max_sim,
               MAX(created_at) AS last_similar
        FROM topic_embeddings
        WHERE text_type = 'topic'
          AND 1 - (embedding <=> $1::vector) > 0.3
    """,
        emb_str,
    )

    our_recency_score = 1.0
    if row and row["last_similar"]:
        days_ago = (datetime.utcnow() - row["last_similar"].replace(tzinfo=None)).days
        our_recency_score = min(1.0, days_ago / 30.0)

    trend_score = min(1.0, max(0.0, (trend_momentum + 1) / 2))

    comp_row = await pool.fetchrow(
        """
        SELECT MAX(published_at) AS last_comp_video
        FROM competitor_videos
        WHERE niche = $1
          AND title ILIKE '%' || $2 || '%'
          AND published_at > NOW() - INTERVAL '30 days'
    """,
        niche,
        topic[:50],
    )

    competitor_freshness = 1.0
    if comp_row and comp_row["last_comp_video"]:
        days = (datetime.utcnow() - comp_row["last_comp_video"].replace(tzinfo=None)).days
        competitor_freshness = min(1.0, days / 14.0)

    freshness = our_recency_score * 0.4 + trend_score * 0.35 + competitor_freshness * 0.25

    result = {
        "freshness_score": round(freshness, 4),
        "our_recency_score": round(our_recency_score, 4),
        "trend_score": round(trend_score, 4),
        "competitor_freshness": round(competitor_freshness, 4),
    }

    logger.info("freshness.computed", topic=topic[:50], score=round(freshness, 3))
    return result
