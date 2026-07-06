"""Niche-saturation scorer (Phase 8).

The forward-looking signal that the rest of the research stack lacks.
``freshness_score`` and ``novelty_score`` measure how new a candidate
topic is relative to *our own* past content. **Saturation** measures how
crowded the topic is in the *external* niche right now — i.e. is the
algorithm already drowning in this exact angle from other creators?

A candidate that scores S-tier on every internal metric but lands in a
saturated topic cluster will under-perform: the YouTube algorithm
preferentially surfaces *novel* angles, not repeated ones.

Algorithm:

1. Embed the candidate topic (uses the existing 384-dim sentence-
   transformer in ``similarity``).
2. Run a pgvector cosine query against ``competitor_videos`` rows from
   the niche, last ``lookback_days`` days, that have an embedding.
3. For each top match, compute a contribution = cosine_similarity ×
   recency_decay × view_velocity_factor.
4. Saturation = clipped sum of contributions, normalised to [0, 1].
5. Return ``saturation_gap = 1 - saturation`` so the opportunity scorer
   can keep its "higher is better" convention without special-casing
   negative weights.

Cold-start safe: if the niche has no embedded videos yet, returns
``saturation_gap = 1.0`` (i.e. don't penalise) and flags the result so
the caller can log "no pulse data."
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import structlog

logger = structlog.get_logger()




DEFAULT_LOOKBACK_DAYS = 14

COSINE_THRESHOLD = 0.55

TOP_K = 20

VELOCITY_REFERENCE = 4_000.0




@dataclass
class _PulseRow:
    """Minimal shape the scorer needs from each competitor video."""
    similarity: float
    view_velocity: float
    age_days: float


@dataclass
class SaturationResult:
    saturation: float
    saturation_gap: float
    n_matches: int
    top_match_similarity: float
    cold_start: bool


def _recency_decay(age_days: float, half_life_days: float = 7.0) -> float:
    """Exponential decay so a 2-week-old video counts ≪ a 1-day-old one.

    Half-life of 7 days mirrors the typical YouTube recommendation
    window: by day 14 (the cutoff we pull at), a video contributes
    only ~25% of what it would at day 0.
    """
    if age_days <= 0:
        return 1.0
    return math.pow(0.5, age_days / max(half_life_days, 0.1))


def _velocity_factor(view_velocity: float) -> float:
    """Map view velocity → [0, 1].

    Logarithmic so a 10× velocity difference maps to roughly +0.3 in the
    factor, not +9.0. Without this, one viral outlier would dominate the
    sum even if it's only loosely on-topic.
    """
    if view_velocity <= 0:
        return 0.0
    return min(1.0, math.log1p(view_velocity) / math.log1p(VELOCITY_REFERENCE))


def compute_saturation_from_pulse(rows: list[_PulseRow]) -> SaturationResult:
    """Pure scorer over already-fetched pulse rows.

    Public for tests; the DB-going wrapper is :func:`compute_saturation`.
    """
    if not rows:
        return SaturationResult(
            saturation=0.0,
            saturation_gap=1.0,
            n_matches=0,
            top_match_similarity=0.0,
            cold_start=True,
        )

    matches = [r for r in rows if r.similarity >= COSINE_THRESHOLD]
    if not matches:
        return SaturationResult(
            saturation=0.0,
            saturation_gap=1.0,
            n_matches=0,
            top_match_similarity=max(r.similarity for r in rows),
            cold_start=False,
        )

    matches.sort(key=lambda r: r.similarity, reverse=True)
    matches = matches[:TOP_K]

    contribution = 0.0
    for r in matches:
        sim = max(0.0, min(1.0, r.similarity))
        contribution += sim * _recency_decay(r.age_days) * _velocity_factor(r.view_velocity)

    saturation = min(1.0, contribution / 5.0)
    return SaturationResult(
        saturation=round(saturation, 4),
        saturation_gap=round(1.0 - saturation, 4),
        n_matches=len(matches),
        top_match_similarity=round(matches[0].similarity, 4),
        cold_start=False,
    )




def _format_vector(emb: list[float]) -> str:
    """Encode a float list as the pgvector literal '[v1,v2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in emb) + "]"


async def compute_saturation(
    topic: str,
    niche: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> SaturationResult:
    """Live saturation score for one (topic, niche) candidate.

    Defensive at every step:
    * empty topic / niche → cold start
    * embedding fails → cold start (logged)
    * DB error → cold start (logged)

    The opportunity scorer treats "cold start" as 1.0 saturation_gap
    (no penalty) — we never want this signal to *block* a topic, only
    to *down-weight* it when there's evidence.
    """
    if not topic or not niche:
        return SaturationResult(0.0, 1.0, 0, 0.0, cold_start=True)

    try:
        from services_api.research.similarity import compute_embedding
        emb = await compute_embedding(topic)
    except Exception as exc:
        logger.warning("saturation.embed_failed", topic=topic[:50], error=str(exc))
        return SaturationResult(0.0, 1.0, 0, 0.0, cold_start=True)

    try:
        from core.db import get_pool
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                1 - (title_embedding <=> $1::vector)         AS similarity,
                COALESCE(view_velocity_24h, 0)::float        AS view_velocity,
                EXTRACT(EPOCH FROM (NOW() - published_at)) / 86400.0 AS age_days
            FROM competitor_videos
            WHERE niche = $2
              AND title_embedding IS NOT NULL
              AND published_at > NOW() - ($3::int * INTERVAL '1 day')
            ORDER BY title_embedding <=> $1::vector
            LIMIT 50
            """,
            _format_vector(emb), niche, lookback_days,
        )
    except Exception as exc:
        logger.warning("saturation.query_failed", niche=niche, error=str(exc))
        return SaturationResult(0.0, 1.0, 0, 0.0, cold_start=True)

    pulse = [
        _PulseRow(
            similarity=float(r["similarity"]),
            view_velocity=float(r["view_velocity"]),
            age_days=float(r["age_days"] or 0.0),
        )
        for r in rows
    ]
    result = compute_saturation_from_pulse(pulse)
    if result.n_matches > 0:
        logger.info("saturation.scored",
                    topic=topic[:60], niche=niche,
                    saturation=result.saturation,
                    matches=result.n_matches,
                    top_sim=result.top_match_similarity)
    return result


async def get_pulse_freshness(niche: str | None = None) -> dict:
    """Aggregate pulse freshness for the fleet-health endpoint.

    Returns total embedded rows + the most recent ``updated_at`` so the
    dashboard can show "pulse data is N hours old."
    """
    try:
        from core.db import get_pool
        pool = await get_pool()
        if niche:
            row = await pool.fetchrow(
                """
                SELECT COUNT(*)::int                AS embedded_rows,
                       MAX(updated_at)              AS last_refresh
                FROM competitor_videos
                WHERE niche = $1 AND title_embedding IS NOT NULL
                """,
                niche,
            )
        else:
            row = await pool.fetchrow(
                """
                SELECT COUNT(*)::int                AS embedded_rows,
                       MAX(updated_at)              AS last_refresh,
                       COUNT(DISTINCT niche)::int   AS niches_with_data
                FROM competitor_videos
                WHERE title_embedding IS NOT NULL
                """
            )
        out = {
            "embedded_rows": int(row["embedded_rows"] or 0),
            "last_refresh":  row["last_refresh"].isoformat() if row["last_refresh"] else None,
        }
        if not niche:
            out["niches_with_data"] = int(row["niches_with_data"] or 0)
        return out
    except Exception as exc:
        return {"embedded_rows": 0, "last_refresh": None, "error": type(exc).__name__}
