"""Burst Detector + Phrase Miner + Seasonality Engine.

- Burst detection: Rolling z-scores on trend signal time-series to detect sudden spikes.
- Phrase mining: Extract rising keyphrases from competitor titles/descriptions.
- Seasonality engine: Calendar-aware scoring with historical performance correlation.

All computation is local. Zero API cost.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta

import numpy as np
import structlog

from src.db import get_pool

logger = structlog.get_logger()


# BURST DETECTION (Kleinberg-inspired rolling z-score)

async def detect_bursts(niche: str, lookback_days: int = 14, z_threshold: float = 2.0) -> list[dict]:
    """Detect bursting keywords in a niche.

    Uses rolling z-scores on Google Trends momentum snapshots.
    A burst = momentum z-score > z_threshold over the lookback window.

    Returns:
        list of dict: [{keyword, burst_score, z_score, momentum, is_burst}]
    """
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT keyword, momentum_score, volume_index, snapshot_date
        FROM trend_signals
        WHERE niche = $1 AND snapshot_date > CURRENT_DATE - $2::int
        ORDER BY keyword, snapshot_date
    """, niche, lookback_days)

    if not rows:
        return []

    # Group by keyword
    kw_series: dict[str, list[float]] = {}
    kw_latest: dict[str, dict] = {}
    for r in rows:
        kw = r["keyword"]
        if kw not in kw_series:
            kw_series[kw] = []
            kw_latest[kw] = {}
        kw_series[kw].append(float(r["momentum_score"]))
        kw_latest[kw] = {"volume": r["volume_index"], "date": r["snapshot_date"]}

    bursts = []
    for kw, series in kw_series.items():
        if len(series) < 3:
            continue

        arr = np.array(series)
        mean = arr[:-1].mean() if len(arr) > 1 else arr.mean()
        std = arr[:-1].std() if len(arr) > 1 else 1.0
        std = max(std, 0.01)  # Avoid division by zero

        latest = arr[-1]
        z = (latest - mean) / std
        burst_score = max(0.0, float(z) / 4.0)  # Normalize to ~0-1 range

        is_burst = z >= z_threshold

        if is_burst:
            await pool.execute("""
                UPDATE trend_signals SET burst_score = $1, is_burst = TRUE
                WHERE niche = $2 AND keyword = $3 AND snapshot_date = $4
            """, burst_score, niche, kw, kw_latest[kw]["date"])

        bursts.append({
            "keyword": kw,
            "z_score": round(float(z), 3),
            "burst_score": round(burst_score, 4),
            "momentum": round(latest, 3),
            "volume": kw_latest[kw].get("volume", 0),
            "is_burst": is_burst,
        })

    bursts.sort(key=lambda x: x["z_score"], reverse=True)

    logger.info("burst.detected", niche=niche,
                total_keywords=len(kw_series),
                bursting=sum(1 for b in bursts if b["is_burst"]))

    return bursts


# PHRASE MINER (rising terms from competitor content)

def _extract_phrases(text: str, min_len: int = 2, max_len: int = 4) -> list[str]:
    """Extract n-gram phrases from text."""
    # Clean and tokenize
    text = re.sub(r"[^\w\s]", "", text.lower())
    tokens = text.split()

    # Remove stopwords (minimal set)
    stops = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "in", "on", "at", "to", "for", "of", "with", "by", "from",
        "and", "or", "but", "not", "no", "so", "if", "as", "it",
        "this", "that", "these", "those", "i", "you", "he", "she",
        "we", "they", "my", "your", "his", "her", "our", "their",
        "do", "does", "did", "will", "would", "can", "could",
        "has", "have", "had", "just", "very", "also", "than",
    }
    tokens = [t for t in tokens if t not in stops and len(t) > 2]

    phrases = []
    for n in range(min_len, max_len + 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            phrases.append(phrase)

    return phrases


async def mine_phrases(niche: str, days: int = 14, top_n: int = 30) -> list[dict]:
    """Mine rising phrases from recent competitor video titles/descriptions.

    Compares phrase frequency in the last `days` vs the previous period
    to identify trending language.

    Returns:
        list of dict: [{phrase, frequency, is_rising, growth_rate}]
    """
    pool = await get_pool()

    # Recent period
    recent = await pool.fetch("""
        SELECT title, description FROM competitor_videos
        WHERE niche = $1 AND published_at > NOW() - ($2 || ' days')::interval
    """, niche, str(days))

    # Previous period (for comparison)
    older = await pool.fetch("""
        SELECT title, description FROM competitor_videos
        WHERE niche = $1
          AND published_at > NOW() - ($2 || ' days')::interval
          AND published_at <= NOW() - ($3 || ' days')::interval
    """, niche, str(days * 2), str(days))

    # Extract phrases
    recent_phrases = Counter()
    for r in recent:
        text = f"{r['title'] or ''} {(r['description'] or '')[:200]}"
        for p in _extract_phrases(text):
            recent_phrases[p] += 1

    older_phrases = Counter()
    for r in older:
        text = f"{r['title'] or ''} {(r['description'] or '')[:200]}"
        for p in _extract_phrases(text):
            older_phrases[p] += 1

    # Find rising phrases (appeared more recently than before)
    results = []
    for phrase, freq in recent_phrases.most_common(top_n * 3):
        if freq < 2:
            continue
        old_freq = older_phrases.get(phrase, 0)
        growth = (freq - old_freq) / max(old_freq, 1)
        is_rising = growth > 0.5 and freq >= 2

        results.append({
            "phrase": phrase,
            "frequency": freq,
            "old_frequency": old_freq,
            "growth_rate": round(growth, 2),
            "is_rising": is_rising,
        })

    results.sort(key=lambda x: (x["is_rising"], x["growth_rate"]), reverse=True)
    results = results[:top_n]

    # Store in phrase_bank
    today = date.today()
    for r in results:
        try:
            await pool.execute("""
                INSERT INTO phrase_bank (niche, phrase, source, frequency, is_rising, first_seen, last_seen)
                VALUES ($1, $2, 'competitor_mining', $3, $4, $5, $5)
                ON CONFLICT (niche, phrase) DO UPDATE SET
                    frequency = EXCLUDED.frequency,
                    is_rising = EXCLUDED.is_rising,
                    last_seen = EXCLUDED.last_seen
            """, niche, r["phrase"], r["frequency"], r["is_rising"], today)
        except Exception:
            pass

    logger.info("phrases.mined", niche=niche,
                total=len(results),
                rising=sum(1 for r in results if r["is_rising"]))

    return results


async def get_rising_phrases(niche: str, limit: int = 15) -> list[str]:
    """Get current rising phrases for a niche from the phrase bank."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT phrase, frequency FROM phrase_bank
        WHERE niche = $1 AND is_rising = TRUE
        ORDER BY frequency DESC, last_seen DESC
        LIMIT $2
    """, niche, limit)
    return [r["phrase"] for r in rows]


# PHRASE NOVELTY

async def compute_phrase_novelty(topic: str, niche: str) -> float:
    """How much does a topic use rising/novel phrases vs saturated ones?

    Higher = topic uses fresh, rising language not yet overused.
    """
    pool = await get_pool()
    topic_phrases = _extract_phrases(topic, min_len=2, max_len=3)

    if not topic_phrases:
        return 0.5

    rising_rows = await pool.fetch("""
        SELECT phrase FROM phrase_bank WHERE niche = $1 AND is_rising = TRUE
    """, niche)
    rising_set = {r["phrase"] for r in rising_rows}

    saturated_rows = await pool.fetch("""
        SELECT phrase FROM phrase_bank
        WHERE niche = $1 AND is_rising = FALSE AND frequency > 5
    """, niche)
    saturated_set = {r["phrase"] for r in saturated_rows}

    rising_hits = sum(1 for p in topic_phrases if p in rising_set)
    saturated_hits = sum(1 for p in topic_phrases if p in saturated_set)

    n = len(topic_phrases)
    novelty = (rising_hits * 2 - saturated_hits) / max(n, 1)
    novelty = max(0.0, min(1.0, (novelty + 1) / 2))  # Normalize to 0-1

    return round(novelty, 4)


# SEASONALITY ENGINE

# Extended seasonal events calendar
SEASONAL_EVENTS = {
    # Month: [(event_name, keywords, boost)]
    1: [
        ("new_year", ["new year", "resolution", "fresh start", "2025", "2026"], 0.9),
        ("winter", ["winter", "cold", "snow", "cozy"], 0.6),
        ("detox", ["detox", "cleanse", "reset", "health"], 0.7),
    ],
    2: [
        ("valentine", ["valentine", "love", "relationship", "dating", "romance"], 0.85),
        ("super_bowl", ["super bowl", "football", "halftime"], 0.7),
    ],
    3: [
        ("womens_day", ["women", "international women", "equality"], 0.7),
        ("spring_start", ["spring", "renewal", "cleaning"], 0.6),
        ("ramadan", ["ramadan", "fasting", "iftar"], 0.6),
    ],
    4: [
        ("earth_day", ["earth", "environment", "climate", "sustainable"], 0.7),
        ("tax_season", ["tax", "filing", "deadline", "refund"], 0.8),
        ("easter", ["easter", "pascha"], 0.5),
    ],
    5: [
        ("mothers_day", ["mother", "mom", "maternal"], 0.8),
        ("graduation", ["graduation", "graduate", "commencement"], 0.7),
        ("memorial", ["memorial", "remember"], 0.5),
    ],
    6: [
        ("fathers_day", ["father", "dad", "paternal"], 0.8),
        ("summer_start", ["summer", "vacation", "travel"], 0.7),
        ("pride", ["pride", "lgbtq", "rainbow"], 0.6),
    ],
    7: [
        ("independence", ["independence", "fourth of july", "4th", "freedom"], 0.7),
        ("summer_peak", ["summer", "beach", "pool", "hot"], 0.6),
    ],
    8: [
        ("back_to_school", ["school", "back to school", "college", "university"], 0.85),
        ("summer_end", ["summer", "last days", "end of summer"], 0.5),
    ],
    9: [
        ("fall_start", ["fall", "autumn", "harvest"], 0.6),
        ("labor_day", ["labor", "work", "career"], 0.5),
    ],
    10: [
        ("halloween", ["halloween", "spooky", "horror", "costume", "scary"], 0.9),
        ("breast_cancer", ["breast cancer", "awareness", "pink"], 0.6),
    ],
    11: [
        ("thanksgiving", ["thanksgiving", "grateful", "turkey", "family"], 0.8),
        ("black_friday", ["black friday", "deals", "shopping", "sale", "cyber monday"], 0.9),
        ("diwali", ["diwali", "festival of lights"], 0.7),
    ],
    12: [
        ("christmas", ["christmas", "xmas", "santa", "gift", "holiday"], 0.95),
        ("year_review", ["year review", "year in review", "best of", "top 10", "wrap up"], 0.85),
        ("new_year_prep", ["new year", "goals", "planning", "2026", "2027"], 0.8),
    ],
}


async def compute_advanced_seasonality(topic: str, niche: str) -> dict:
    """Compute seasonality score with event matching and historical boost.

    Returns:
        dict with seasonality_score, matched_events, planning_horizon.
    """
    today = date.today()
    month = today.month
    day = today.day
    text = topic.lower()

    matched = []
    max_boost = 0.3  # Default (evergreen)

    # Check current month
    for event_name, keywords, boost in SEASONAL_EVENTS.get(month, []):
        if any(kw in text for kw in keywords):
            matched.append({"event": event_name, "boost": boost, "timing": "current"})
            max_boost = max(max_boost, boost)

    # Check next month (planning ahead)
    next_month = (month % 12) + 1
    for event_name, keywords, boost in SEASONAL_EVENTS.get(next_month, []):
        if any(kw in text for kw in keywords):
            matched.append({"event": event_name, "boost": boost * 0.8, "timing": "upcoming"})
            max_boost = max(max_boost, boost * 0.8)

    # Check historical performance correlation for this niche + month
    pool = await get_pool()
    hist_row = await pool.fetchrow("""
        SELECT AVG(CASE WHEN po.is_success THEN 1.0 ELSE 0.0 END) AS success_rate
        FROM research_features rf
        JOIN performance_outcomes po ON rf.content_id = po.content_id
        WHERE rf.channel_id IN (SELECT channel_id FROM channels WHERE niche = $1)
          AND EXTRACT(MONTH FROM rf.created_at) = $2
          AND po.is_success IS NOT NULL
    """, niche, month)

    hist_boost = 0.0
    if hist_row and hist_row["success_rate"] is not None:
        # If this month historically has above-average success, boost seasonality
        hist_boost = max(0.0, float(hist_row["success_rate"]) - 0.5) * 0.5

    final_score = min(1.0, max_boost + hist_boost)

    result = {
        "seasonality_score": round(final_score, 4),
        "matched_events": matched,
        "historical_boost": round(hist_boost, 4),
        "planning_horizon": f"current={month}, next={next_month}",
    }

    logger.info("seasonality.computed", topic=topic[:40],
                score=round(final_score, 3), events=len(matched))

    return result
