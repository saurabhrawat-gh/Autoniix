"""SEO Optimizer — Optimizes YouTube metadata for discoverability.

Local NLP-based SEO scoring and optimization:
- Title power word detection
- Description keyword optimization
- Tag relevance scoring
- Upload timing prediction based on historical patterns

Intelligence cost: $0.00 — all computation is local.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import numpy as np
import structlog

from core.db import get_pool

logger = structlog.get_logger()

POWER_WORDS = {
    "secret", "shocking", "revealed", "truth", "never", "instantly",
    "proven", "warning", "mistake", "surprising", "hidden", "deadly",
    "urgent", "breaking", "banned", "exposed", "finally", "ultimate",
    "insane", "unbelievable", "illegal", "dangerous", "destroyed",
}

CATEGORY_MAP = {
    "health": "26",
    "tech": "28",
    "finance": "22",
    "education": "27",
    "entertainment": "24",
    "gaming": "20",
    "music": "10",
    "sports": "17",
    "news": "25",
}


def score_title_seo(title: str) -> dict:
    """Score title for YouTube SEO factors."""
    score = 5.0
    factors = []

    words = title.split()
    word_count = len(words)

    char_count = len(title)
    if 40 <= char_count <= 70:
        score += 1.5
        factors.append("Good title length")
    elif char_count > 100:
        score -= 1.0
        factors.append("Title too long — may be truncated")
    elif char_count < 20:
        score -= 0.5
        factors.append("Title too short")

    title_lower = title.lower()
    power_found = [w for w in POWER_WORDS if w in title_lower]
    if power_found:
        score += min(1.5, len(power_found) * 0.5)
        factors.append(f"Power words: {', '.join(power_found[:3])}")

    has_number = any(c.isdigit() for c in title)
    if has_number:
        score += 1.0
        factors.append("Contains number (CTR boost)")

    if "?" in title:
        score += 0.5
        factors.append("Question format (curiosity trigger)")

    caps_words = [w for w in words if w.isupper() and len(w) > 1]
    if 1 <= len(caps_words) <= 2:
        score += 0.5
        factors.append("Strategic caps for emphasis")
    elif len(caps_words) > 2:
        score -= 0.5
        factors.append("Too many ALL CAPS words — looks spammy")

    if re.search(r'[\[\(].*[\]\)]', title):
        score += 0.5
        factors.append("Brackets detected (SEO boost pattern)")

    score = max(1.0, min(10.0, round(score, 1)))

    return {
        "seo_score": score,
        "factors": factors,
        "word_count": word_count,
        "char_count": char_count,
        "has_number": has_number,
        "has_question": "?" in title,
        "power_words_count": len(power_found),
    }


def optimize_description(description: str, title: str, tags: list[str],
                          niche: str = "") -> dict:
    """Optimize YouTube description for SEO."""
    suggestions = []

    desc_length = len(description)
    if desc_length < 200:
        suggestions.append("Description too short — aim for 500+ characters for SEO")
    elif desc_length < 500:
        suggestions.append("Description could be longer — 500-2000 chars is optimal")

    title_words = set(w.lower() for w in title.split() if len(w) > 3)
    desc_lower = description.lower()
    missing_keywords = [w for w in title_words if w not in desc_lower]
    if missing_keywords:
        suggestions.append(f"Add title keywords to description: {', '.join(missing_keywords[:5])}")

    tag_words = set(t.lower() for t in tags)
    missing_tags = [t for t in tag_words if t.lower() not in desc_lower]
    if missing_tags and len(missing_tags) > len(tags) * 0.5:
        suggestions.append("Include more tags in description for keyword density")

    total_words = len(description.split())
    if total_words > 0:
        keyword_matches = sum(1 for w in description.lower().split() if w in title_words)
        density = keyword_matches / total_words
    else:
        density = 0

    return {
        "description_length": desc_length,
        "keyword_density": round(density, 4),
        "suggestions": suggestions,
        "score": round(min(10.0, 5.0 + (1.0 if desc_length >= 500 else 0) +
                          (1.0 if not missing_keywords else 0) +
                          (1.0 if density > 0.02 else 0)), 1),
    }


def suggest_tags(title: str, niche: str, existing_tags: list[str],
                  max_tags: int = 30) -> list[str]:
    """Suggest optimized tags based on title and niche."""
    tags = [str(t) for t in existing_tags]

    title_words = [w.strip(".,!?:;") for w in title.split() if len(w) > 2]
    for word in title_words:
        if word.lower() not in [t.lower() for t in tags]:
            tags.append(word.lower())

    niche_tags = {
        "health": ["health", "wellness", "medical", "body", "science"],
        "tech": ["technology", "tech", "gadgets", "digital", "innovation"],
        "finance": ["money", "finance", "investing", "wealth", "savings"],
        "education": ["education", "learning", "tutorial", "explained", "how to"],
    }
    for tag in niche_tags.get(niche, []):
        if tag not in [t.lower() for t in tags]:
            tags.append(tag)

    if len(title_words) >= 2:
        for i in range(len(title_words) - 1):
            phrase = f"{title_words[i]} {title_words[i+1]}".lower()
            if phrase not in [t.lower() for t in tags]:
                tags.append(phrase)

    return tags[:max_tags]


async def predict_optimal_upload_time(channel_id: str) -> dict:
    """Predict optimal upload time based on historical performance."""
    try:
        pool = await get_pool()

        rows = await pool.fetch("""
            SELECT df.upload_hour_utc, df.upload_day_of_week,
                   df.first_hour_views, df.first_day_views
            FROM delivery_features df
            WHERE df.channel_id = $1
            AND df.first_hour_views IS NOT NULL
            ORDER BY df.created_at DESC LIMIT 50
        """, channel_id)

        if len(rows) < 5:
            return {
                "optimal_hour_utc": 14,
                "optimal_day": 2,
                "confidence": "low",
                "reason": "Insufficient data — using industry default",
            }

        hour_perf: dict[int, list[int]] = {}
        for r in rows:
            h = r["upload_hour_utc"]
            views = r["first_hour_views"] or 0
            if h is not None:
                if h not in hour_perf:
                    hour_perf[h] = []
                hour_perf[h].append(views)

        best_hour = max(hour_perf, key=lambda h: np.mean(hour_perf[h])) if hour_perf else 14

        day_perf: dict[int, list[int]] = {}
        for r in rows:
            d = r["upload_day_of_week"]
            views = r["first_day_views"] or 0
            if d is not None:
                if d not in day_perf:
                    day_perf[d] = []
                day_perf[d].append(views)

        best_day = max(day_perf, key=lambda d: np.mean(day_perf[d])) if day_perf else 2

        return {
            "optimal_hour_utc": best_hour,
            "optimal_day": best_day,
            "confidence": "high" if len(rows) >= 20 else "medium",
            "reason": f"Based on {len(rows)} historical uploads",
            "hours_analyzed": len(hour_perf),
        }

    except Exception as e:
        logger.warning("seo.upload_time_failed", error=str(e))
        return {"optimal_hour_utc": 14, "optimal_day": 2, "confidence": "fallback"}


async def store_delivery_features(content_id: str, channel_id: str,
                                   title: str, description: str,
                                   tags: list[str], seo_result: dict) -> None:
    """Store delivery features for learning."""
    try:
        pool = await get_pool()
        now = datetime.utcnow()
        await pool.execute("""
            INSERT INTO delivery_features (content_id, channel_id,
                upload_hour_utc, upload_day_of_week,
                title_word_count, title_has_number, title_has_question,
                title_power_words, description_length, tag_count,
                seo_score, keyword_density)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
            content_id, channel_id,
            now.hour, now.weekday(),
            seo_result.get("word_count", len(title.split())),
            seo_result.get("has_number", False),
            seo_result.get("has_question", False),
            seo_result.get("power_words_count", 0),
            len(description), len(tags),
            seo_result.get("seo_score", 5.0),
            0.0,
        )
    except Exception as e:
        logger.warning("seo.store_features_failed", error=str(e))
