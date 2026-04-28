"""Opportunity Scorer — Multi-signal ranking for topic candidates.

Combines freshness, novelty, trend momentum, supply-demand gap,
hookability, competitor gap, burst score, seasonality, and phrase novelty
into a single opportunity_score. Weights are configurable via system_config
and updated by the self-learning model.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime

import structlog

from src.db import get_pool

logger = structlog.get_logger()

# Default weights (overridden from system_config or ML model)
DEFAULT_WEIGHTS = {
    "freshness": 0.18,
    "novelty": 0.15,
    "trend_momentum": 0.18,
    "supply_demand_gap": 0.12,
    "hookability": 0.12,
    "competitor_gap": 0.08,
    "burst_score": 0.07,
    "seasonality": 0.05,
    "phrase_novelty": 0.05,
}


async def _load_weights(niche: str | None = None) -> dict:
    """Load scoring weights from system_config or ML model store."""
    pool = await get_pool()

    # Try niche-specific learned weights first
    if niche:
        row = await pool.fetchrow("""
            SELECT metrics FROM ml_models
            WHERE model_name = 'opportunity_weights' AND niche = $1 AND is_active = TRUE
            ORDER BY model_version DESC LIMIT 1
        """, niche)
        if row and row["metrics"]:
            learned = json.loads(row["metrics"]) if isinstance(row["metrics"], str) else row["metrics"]
            if "weights" in learned:
                return learned["weights"]

    # Fall back to system_config global weights
    row = await pool.fetchrow("""
        SELECT config_value FROM system_config WHERE config_key = 'opportunity_weights'
    """)
    if row:
        try:
            return json.loads(row["config_value"])
        except (json.JSONDecodeError, TypeError):
            pass

    return DEFAULT_WEIGHTS.copy()


# ── Hookability Heuristics ──────────────────────────────────

def compute_hookability(title: str, hook: str = "") -> float:
    """Score hookability of a title/hook based on heuristics.

    Checks for: curiosity gap, numbers, controversy signals,
    emotional words, question format, power words.
    """
    text = f"{title} {hook}".lower()
    score = 0.0
    checks = 0

    # Curiosity gap patterns
    curiosity_patterns = [
        "why", "how", "what if", "secret", "hidden", "truth",
        "nobody", "no one", "revealed", "shocking", "surprising",
    ]
    if any(p in text for p in curiosity_patterns):
        score += 1.0
    checks += 1

    # Numbers (listicles, specifics)
    import re
    if re.search(r"\d+", text):
        score += 0.8
    checks += 1

    # Question format (drives curiosity)
    if "?" in text:
        score += 0.7
    checks += 1

    # Controversy / debate signals
    controversy = ["myth", "wrong", "lie", "debate", "controversial", "unpopular", "overrated"]
    if any(p in text for p in controversy):
        score += 0.9
    checks += 1

    # Emotional intensity words
    emotional = ["amazing", "incredible", "terrifying", "beautiful", "insane",
                 "genius", "brilliant", "devastating", "powerful", "mind-blowing"]
    if any(p in text for p in emotional):
        score += 0.8
    checks += 1

    # Power words (urgency/exclusivity)
    power = ["ultimate", "complete", "essential", "proven", "guaranteed", "exclusive", "urgent"]
    if any(p in text for p in power):
        score += 0.7
    checks += 1

    # Length check: good titles are 40-70 chars
    if 40 <= len(title) <= 70:
        score += 0.6
    checks += 1

    return round(min(1.0, score / max(checks * 0.5, 1)), 4)


# ── Supply-Demand Gap ───────────────────────────────────────

async def compute_supply_demand_gap(
    topic: str,
    niche: str,
    trend_volume: int = 0,
) -> float:
    """Estimate supply-demand gap.

    High demand (trend volume) + low supply (few recent competitor videos on topic) = high gap.
    """
    pool = await get_pool()

    # Supply: count recent competitor videos with similar titles
    supply_count = await pool.fetchval("""
        SELECT COUNT(*) FROM competitor_videos
        WHERE niche = $1
          AND title ILIKE '%' || $2 || '%'
          AND published_at > NOW() - INTERVAL '30 days'
    """, niche, topic[:50])

    # Demand proxy: trend volume index (0-100 from Google Trends)
    demand = min(1.0, trend_volume / 100.0) if trend_volume > 0 else 0.5

    # Supply penalty: more supply = lower gap
    supply_penalty = min(1.0, supply_count / 10.0) if supply_count else 0.0

    gap = max(0.0, demand - supply_penalty * 0.6)
    return round(gap, 4)


# ── Seasonality ─────────────────────────────────────────────

def compute_seasonality(topic: str) -> float:
    """Basic seasonality scoring based on calendar signals.

    Checks if the topic relates to current season, upcoming events,
    or recurring patterns.
    """
    today = date.today()
    month = today.month
    text = topic.lower()

    # Monthly themes
    monthly_themes = {
        1: ["new year", "resolution", "fresh start", "winter"],
        2: ["valentine", "love", "relationship"],
        3: ["spring", "women", "march madness"],
        4: ["tax", "spring", "earth day"],
        5: ["summer", "memorial", "graduation"],
        6: ["summer", "father", "travel"],
        7: ["summer", "independence", "vacation"],
        8: ["back to school", "summer"],
        9: ["fall", "autumn", "back to school"],
        10: ["halloween", "spooky", "horror", "fall"],
        11: ["thanksgiving", "black friday", "gratitude"],
        12: ["christmas", "holiday", "year review", "new year"],
    }

    themes = monthly_themes.get(month, [])
    if any(t in text for t in themes):
        return 0.85

    # Also check next month for planning ahead
    next_month = (month % 12) + 1
    next_themes = monthly_themes.get(next_month, [])
    if any(t in text for t in next_themes):
        return 0.65

    return 0.3  # Evergreen default


# ── Main Scorer ─────────────────────────────────────────────

async def score_opportunity(
    topic: str,
    title: str = "",
    hook: str = "",
    niche: str = "",
    features: dict | None = None,
) -> dict:
    """Compute the final opportunity score for a topic candidate.

    Args:
        topic: The candidate topic.
        title: Proposed title.
        hook: Proposed hook line.
        niche: Channel niche.
        features: Pre-computed feature dict (freshness_score, novelty_score,
                  trend_momentum, burst_score, phrase_novelty).

    Returns:
        dict with opportunity_score, feature breakdown, weights used.
    """
    features = features or {}
    weights = await _load_weights(niche)

    # Compute missing features
    freshness = features.get("freshness_score", 0.5)
    novelty = features.get("novelty_score", 0.5)
    trend_momentum = features.get("trend_momentum", 0.0)
    burst = features.get("burst_score", 0.0)
    phrase_nov = features.get("phrase_novelty", 0.5)

    hookability = compute_hookability(title or topic, hook)

    trend_vol = int(features.get("trend_volume_index", 50))
    sdg = await compute_supply_demand_gap(topic, niche, trend_vol)

    # Competitor gap: derived from novelty + supply-demand
    comp_gap = min(1.0, (novelty + sdg) / 2)

    seasonality = compute_seasonality(topic)

    # Build feature vector
    feature_vec = {
        "freshness": freshness,
        "novelty": novelty,
        "trend_momentum": min(1.0, max(0.0, (trend_momentum + 1) / 2)),
        "supply_demand_gap": sdg,
        "hookability": hookability,
        "competitor_gap": comp_gap,
        "burst_score": min(1.0, burst),
        "seasonality": seasonality,
        "phrase_novelty": phrase_nov,
    }

    # Weighted sum
    opportunity = sum(
        feature_vec.get(k, 0) * weights.get(k, 0)
        for k in weights
    )
    # Clamp to [0, 1]
    opportunity = round(max(0.0, min(1.0, opportunity)), 4)

    result = {
        "opportunity_score": opportunity,
        "features": feature_vec,
        "weights": weights,
    }

    logger.info("opportunity.scored", topic=topic[:50], score=opportunity)
    return result


async def rank_candidates(
    candidates: list[dict],
    niche: str,
) -> list[dict]:
    """Score and rank a list of topic candidates.

    Each candidate dict should have: topic, title (optional), hook (optional),
    and any pre-computed features.

    Returns sorted list (highest opportunity_score first).
    """
    for c in candidates:
        result = await score_opportunity(
            topic=c.get("topic", c.get("title", "")),
            title=c.get("title", ""),
            hook=c.get("hook", ""),
            niche=niche,
            features=c.get("features", {}),
        )
        c["opportunity_score"] = result["opportunity_score"]
        c["feature_breakdown"] = result["features"]

    candidates.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    return candidates


async def store_research_features(
    content_id: str,
    channel_id: str,
    topic: str,
    features: dict,
    opportunity_score: float,
    model_predicted: float | None = None,
    bandit_arm: str | None = None,
    was_selected: bool = False,
) -> None:
    """Persist feature row for ML training later."""
    pool = await get_pool()
    try:
        await pool.execute("""
            INSERT INTO research_features
                (content_id, channel_id, topic, freshness_score, novelty_score,
                 trend_momentum, supply_demand_gap, hookability_score, competitor_gap,
                 burst_score, seasonality_score, phrase_novelty, opportunity_score,
                 model_predicted, bandit_arm, was_selected)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        """,
            content_id, channel_id, topic,
            features.get("freshness", 0), features.get("novelty", 0),
            features.get("trend_momentum", 0), features.get("supply_demand_gap", 0),
            features.get("hookability", 0), features.get("competitor_gap", 0),
            features.get("burst_score", 0), features.get("seasonality", 0),
            features.get("phrase_novelty", 0), opportunity_score,
            model_predicted, bandit_arm, was_selected,
        )
    except Exception as e:
        logger.warning("opportunity.store_features_failed", error=str(e))
