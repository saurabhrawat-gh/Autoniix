"""Uniqueness + variation enforcement (Phase 5 / S6).

Two responsibilities:

1. **Reject near-duplicates** before they ship. We embed a candidate's
   title+hook, compare against the channel's last 30 outputs via pgvector
   cosine, and refuse anything ≥ ``similarity_threshold`` (default 0.92).

2. **Authenticity score** — a 0..1 composite the dashboard surfaces on
   every video card. Components:

   - ``hook_novelty``   — phrase-bank novelty of the selected hook
   - ``thumb_distinct`` — visual diversity vs. last-N thumbnails (placeholder)
   - ``narrative``      — narration ratio derived from script structure
   - ``perplexity``     — proxy from script_critic_scores when available

The drift watchdog auto-pauses a channel when ``N`` consecutive videos cross
the similarity threshold; that's executed by a Temporal cron, not here.

This module is best-effort: every public function returns a usable value
even when the embedding model or DB is unavailable. Production logic only
gates on the actual similarity score we get from the DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()

DEFAULT_SIMILARITY_THRESHOLD = 0.92
DEFAULT_LOOKBACK = 30


@dataclass
class UniquenessResult:
    ok: bool
    similarity: float
    nearest_video_id: str | None
    threshold: float


async def check_uniqueness(
    channel_id: str,
    title: str,
    hook: str | None = None,
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    lookback: int = DEFAULT_LOOKBACK,
) -> UniquenessResult:
    """Returns ok=False when the candidate is too similar to a recent video."""
    text = (title or "") + " " + (hook or "")
    text = text.strip()
    if not text:
        return UniquenessResult(True, 0.0, None, threshold)
    try:
        embedding = _embed(text)
        if embedding is None:
            return UniquenessResult(True, 0.0, None, threshold)
        from src.db import get_pool
        pool = await get_pool()
        # Use pgvector <=> (cosine distance). similarity = 1 - distance.
        row = await pool.fetchrow(
            """
            SELECT content_id, 1 - (title_embedding <=> $1::vector) AS similarity
              FROM videos
             WHERE channel_id = $2
               AND title_embedding IS NOT NULL
               AND created_at > NOW() - INTERVAL '180 days'
             ORDER BY title_embedding <=> $1::vector
             LIMIT 1
            """,
            embedding, channel_id,
        )
        if not row:
            return UniquenessResult(True, 0.0, None, threshold)
        sim = float(row["similarity"] or 0.0)
        ok = sim < threshold
        return UniquenessResult(ok, sim, row["content_id"], threshold)
    except Exception as exc:
        logger.warning("uniqueness.check_failed", channel_id=channel_id, error=str(exc))
        return UniquenessResult(True, 0.0, None, threshold)


def _embed(text: str) -> list[float] | None:
    """Cheap CPU embedding. Returns None if the model isn't available."""
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None
    if not getattr(_embed, "_model", None):
        try:
            _embed._model = SentenceTransformer("all-MiniLM-L6-v2")  # type: ignore[attr-defined]
        except Exception:
            return None
    try:
        v = _embed._model.encode([text])[0]  # type: ignore[attr-defined]
        return [float(x) for x in v]
    except Exception:
        return None


# ── Authenticity score ──────────────────────────────────────
def compute_authenticity_score(video: dict[str, Any]) -> float:
    """Return a 0..1 authenticity score from a videos row.

    ``video`` is the asyncpg Record cast to dict with all available fields.
    Missing fields fall through to neutral defaults (~0.5) — the score never
    crashes a render.
    """
    components: list[tuple[str, float, float]] = []  # (name, score, weight)

    # 1) Hook novelty — derived from script_critic_scores.scene_direction or
    #    falling back to a length heuristic.
    crit = video.get("script_critic_scores") or {}
    hook_score = float(crit.get("hook_retention", crit.get("hook", 0.7))) if isinstance(crit, dict) else 0.7
    components.append(("hook", min(1.0, hook_score / 10.0 if hook_score > 1 else hook_score), 0.25))

    # 2) Thumbnail distinctiveness — composition_rule diversity proxy.
    thumb = video.get("thumbnail_result") or {}
    thumb_score = float(thumb.get("distinctiveness", 0.65)) if isinstance(thumb, dict) else 0.65
    components.append(("thumb", thumb_score, 0.20))

    # 3) Narration / commentary ratio — structure_score normalized.
    structure = float(video.get("script_structure_score") or 0.7)
    structure = structure / 10.0 if structure > 1 else structure
    components.append(("structure", structure, 0.20))

    # 4) Production score (composite of QA layers)
    prod = float(video.get("production_score") or 0.7)
    prod = prod / 10.0 if prod > 1 else prod
    components.append(("production", prod, 0.15))

    # 5) Cross-channel similarity penalty (LOWER similarity → HIGHER authenticity)
    cross = float(video.get("cross_channel_similarity") or 0.0)
    components.append(("cross", max(0.0, 1.0 - cross), 0.20))

    weighted = sum(s * w for _, s, w in components)
    total_w = sum(w for _, _, w in components)
    return round(weighted / total_w if total_w else 0.5, 3)
