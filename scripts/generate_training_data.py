#!/usr/bin/env python3
"""Generate synthetic training data to bootstrap GBM models.

Creates realistic feature+outcome rows per niche:
- Voice features + retention outcomes
- Thumbnail features + CTR outcomes
- Script features + engagement outcomes
- Research features + performance outcomes
- Delivery features + view outcomes

Usage:
    python -m scripts.generate_training_data --niches tech,health,finance --count 60

This populates the DB tables so GBM models can be trained immediately
without waiting for 50+ real videos.  As real data accumulates, synthetic
rows get progressively outweighed (older rows receive lower weight during
training).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_pool, close_pool

# Niche-specific distributions
# These model real YouTube performance distributions per niche.

NICHE_PROFILES = {
    "tech": {
        "avg_views": 5000, "std_views": 8000,
        "avg_ctr": 0.06, "std_ctr": 0.025,
        "avg_retention": 0.42, "std_retention": 0.12,
        "common_emotions": ["curiosity", "excitement", "authority", "surprise"],
        "avg_duration_s": 480, "std_duration_s": 180,
    },
    "health": {
        "avg_views": 8000, "std_views": 12000,
        "avg_ctr": 0.07, "std_ctr": 0.03,
        "avg_retention": 0.38, "std_retention": 0.15,
        "common_emotions": ["empathy", "concern", "authority", "surprise"],
        "avg_duration_s": 600, "std_duration_s": 200,
    },
    "finance": {
        "avg_views": 4000, "std_views": 6000,
        "avg_ctr": 0.055, "std_ctr": 0.02,
        "avg_retention": 0.35, "std_retention": 0.10,
        "common_emotions": ["urgency", "authority", "fear", "excitement"],
        "avg_duration_s": 540, "std_duration_s": 150,
    },
    "education": {
        "avg_views": 6000, "std_views": 10000,
        "avg_ctr": 0.065, "std_ctr": 0.025,
        "avg_retention": 0.40, "std_retention": 0.13,
        "common_emotions": ["curiosity", "authority", "empathy", "joy"],
        "avg_duration_s": 720, "std_duration_s": 240,
    },
    "entertainment": {
        "avg_views": 10000, "std_views": 20000,
        "avg_ctr": 0.08, "std_ctr": 0.035,
        "avg_retention": 0.45, "std_retention": 0.15,
        "common_emotions": ["excitement", "surprise", "joy", "curiosity"],
        "avg_duration_s": 420, "std_duration_s": 120,
    },
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _gen_voice_row(i: int, niche: str, profile: dict, channel_id: str) -> dict:
    """Generate one synthetic voice_features + voice_outcomes row."""
    emotions = profile["common_emotions"]
    emotion_variety = random.uniform(0.3, 0.8)
    stability = random.gauss(0.48, 0.08)
    similarity = random.gauss(0.73, 0.06)
    style = random.gauss(0.42, 0.10)
    speed = random.gauss(1.02, 0.08)
    emphasis_density = random.uniform(0.5, 2.5)
    pause_ms = random.gauss(320, 60)
    snr = random.gauss(28, 5)
    rms = random.gauss(0.06, 0.02)
    naturalness = random.gauss(7.5, 1.2)
    wpm = random.gauss(155, 20)
    duration = max(30, random.gauss(profile["avg_duration_s"], profile["std_duration_s"]))
    seg_count = max(3, int(duration / 30))

    # Outcome: retention correlates with naturalness, emotion variety, good speed
    base_retention = profile["avg_retention"]
    retention = base_retention + (naturalness - 7.0) * 0.02 + (emotion_variety - 0.5) * 0.05
    retention = _clamp(retention + random.gauss(0, 0.05), 0.10, 0.85)

    return {
        "features": {
            "avg_stability": round(_clamp(stability, 0.1, 0.9), 4),
            "avg_similarity_boost": round(_clamp(similarity, 0.3, 1.0), 4),
            "avg_style": round(_clamp(style, 0.1, 0.9), 4),
            "avg_speed": round(_clamp(speed, 0.7, 1.4), 4),
            "emotion_variety": round(_clamp(emotion_variety, 0.1, 1.0), 4),
            "emphasis_density": round(_clamp(emphasis_density, 0.0, 5.0), 4),
            "avg_pause_ms": round(_clamp(pause_ms, 100, 800), 1),
            "snr_db": round(_clamp(snr, 10, 50), 2),
            "rms_energy": round(_clamp(rms, 0.01, 0.15), 4),
            "naturalness_score": round(_clamp(naturalness, 3.0, 10.0), 2),
            "wpm": round(_clamp(wpm, 100, 220), 1),
            "total_duration_s": round(duration, 1),
            "segment_count": seg_count,
        },
        "outcome": {
            "avg_retention_rate": round(retention, 4),
            "watch_time_ratio": round(retention * random.uniform(0.8, 1.2), 4),
        },
        "niche": niche,
        "channel_id": channel_id,
        "content_id": f"SYN_VOICE_{niche}_{i:03d}",
    }


def _gen_thumbnail_row(i: int, niche: str, profile: dict, channel_id: str) -> dict:
    """Generate one synthetic thumbnail_features + outcome row."""
    has_face = random.random() < 0.65
    face_area = random.uniform(0.05, 0.35) if has_face else 0.0
    text_words = random.randint(1, 6)
    text_area = min(0.4, text_words * 0.06)
    brightness = random.gauss(0.55, 0.15)
    saturation = random.gauss(0.50, 0.15)
    contrast = random.gauss(4.0, 1.5)
    rot_score = random.gauss(6.5, 2.0)
    comp_score = random.gauss(7.0, 1.5)

    # CTR correlates with: face presence, brightness, saturation, composition
    base_ctr = profile["avg_ctr"]
    ctr = base_ctr + (0.015 if has_face else -0.005)
    ctr += (_clamp(brightness, 0, 1) - 0.5) * 0.02
    ctr += (_clamp(saturation, 0, 1) - 0.5) * 0.015
    ctr += (comp_score - 7.0) * 0.005
    ctr = _clamp(ctr + random.gauss(0, 0.01), 0.01, 0.20)

    return {
        "features": {
            "has_face": has_face,
            "face_area_ratio": round(_clamp(face_area, 0, 0.5), 4),
            "text_area_ratio": round(_clamp(text_area, 0, 0.5), 4),
            "color_contrast_score": round(_clamp(contrast, 0.5, 10), 2),
            "brightness_score": round(_clamp(brightness, 0, 1), 4),
            "saturation_score": round(_clamp(saturation, 0, 1), 4),
            "rule_of_thirds_score": round(_clamp(rot_score, 1, 10), 2),
            "text_word_count": text_words,
            "local_composition_score": round(_clamp(comp_score, 1, 10), 2),
        },
        "outcome": {
            "actual_ctr": round(ctr, 5),
            "impressions": random.randint(500, 50000),
        },
        "niche": niche,
        "channel_id": channel_id,
        "content_id": f"SYN_THUMB_{niche}_{i:03d}",
    }


def _gen_delivery_row(i: int, niche: str, profile: dict, channel_id: str) -> dict:
    """Generate one synthetic delivery_features + outcome row."""
    hour = random.randint(0, 23)
    day = random.randint(0, 6)
    word_count = random.randint(4, 12)
    has_number = random.random() < 0.4
    has_question = random.random() < 0.25
    power_words = random.randint(0, 3)
    desc_len = random.randint(100, 2000)
    tag_count = random.randint(5, 25)
    seo_score = random.gauss(6.5, 1.5)

    # Views correlate with: time of day, SEO, power words
    best_hours = {13, 14, 15, 16, 17}
    best_days = {1, 2, 3}  # Tue-Thu
    views = max(100, int(random.gauss(profile["avg_views"], profile["std_views"])))
    if hour in best_hours:
        views = int(views * 1.3)
    if day in best_days:
        views = int(views * 1.15)

    first_hour = int(views * random.uniform(0.05, 0.15))
    first_day = int(views * random.uniform(0.3, 0.6))

    return {
        "features": {
            "upload_hour_utc": hour,
            "upload_day_of_week": day,
            "title_word_count": word_count,
            "title_has_number": has_number,
            "title_has_question": has_question,
            "title_power_words": power_words,
            "description_length": desc_len,
            "tag_count": tag_count,
            "seo_score": round(_clamp(seo_score, 1, 10), 2),
        },
        "outcome": {
            "first_hour_views": first_hour,
            "first_day_views": first_day,
            "total_views_7d": views,
        },
        "niche": niche,
        "channel_id": channel_id,
        "content_id": f"SYN_DELIV_{niche}_{i:03d}",
    }


def _gen_feedback_row(i: int, niche: str, profile: dict, channel_id: str) -> dict:
    """Generate one synthetic feedback_loop row for pattern mining."""
    idea = random.gauss(7.5, 1.0)
    script = random.gauss(7.8, 1.0)
    thumbnail = random.gauss(7.5, 1.2)
    hook = random.gauss(7.0, 1.5)
    final = (idea + script + thumbnail + hook) / 4

    views = max(100, int(random.gauss(profile["avg_views"], profile["std_views"])))
    likes = int(views * random.uniform(0.02, 0.08))
    comments = int(views * random.uniform(0.003, 0.02))
    engagement = (likes + comments) / max(views, 1)

    tier = "viral" if views > profile["avg_views"] * 3 else \
           "good" if views > profile["avg_views"] else \
           "average" if views > profile["avg_views"] * 0.3 else "low"

    return {
        "content_id": f"SYN_FB_{niche}_{i:03d}",
        "channel_id": channel_id,
        "title": f"Synthetic Video {niche.title()} #{i}",
        "idea_score": round(_clamp(idea, 3, 10), 2),
        "script_score": round(_clamp(script, 3, 10), 2),
        "thumbnail_score": round(_clamp(thumbnail, 3, 10), 2),
        "hook_retention_score": round(_clamp(hook, 3, 10), 2),
        "final_score": round(_clamp(final, 3, 10), 2),
        "yt_views": views,
        "yt_likes": likes,
        "yt_comments": comments,
        "engagement_rate": round(engagement, 5),
        "performance_tier": tier,
        "content_mode": random.choice(["short", "long_form"]),
        "niche": niche,
    }


# DB insertion

async def _insert_voice_data(pool, rows: list[dict]):
    for r in rows:
        f = r["features"]
        o = r["outcome"]
        await pool.execute("""
            INSERT INTO voice_features (content_id, channel_id,
                avg_stability, avg_similarity_boost, avg_style, avg_speed,
                emotion_variety, emphasis_density, avg_pause_ms,
                snr_db, rms_energy, naturalness_score, wpm, total_duration_s, segment_count)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT DO NOTHING
        """, r["content_id"], r["channel_id"],
            f["avg_stability"], f["avg_similarity_boost"], f["avg_style"], f["avg_speed"],
            f["emotion_variety"], f["emphasis_density"], f["avg_pause_ms"],
            f["snr_db"], f["rms_energy"], f["naturalness_score"],
            f["wpm"], f["total_duration_s"], f["segment_count"])

        await pool.execute("""
            INSERT INTO voice_outcomes (content_id, channel_id,
                avg_retention_rate, watch_time_ratio, is_synthetic)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT DO NOTHING
        """, r["content_id"], r["channel_id"],
            o["avg_retention_rate"], o["watch_time_ratio"])


async def _insert_thumbnail_data(pool, rows: list[dict]):
    for r in rows:
        f = r["features"]
        o = r["outcome"]
        await pool.execute("""
            INSERT INTO thumbnail_features (content_id, channel_id, variant_id,
                has_face, face_area_ratio, text_area_ratio,
                color_contrast_score, brightness_score, saturation_score,
                rule_of_thirds_score, text_word_count,
                local_composition_score, predicted_ctr)
            VALUES ($1,$2,0,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT DO NOTHING
        """, r["content_id"], r["channel_id"],
            f["has_face"], f["face_area_ratio"], f["text_area_ratio"],
            f["color_contrast_score"], f["brightness_score"], f["saturation_score"],
            f["rule_of_thirds_score"], f["text_word_count"],
            f["local_composition_score"], o["actual_ctr"])

        await pool.execute("""
            INSERT INTO thumbnail_outcomes (content_id, channel_id,
                actual_ctr, impressions, is_synthetic)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT DO NOTHING
        """, r["content_id"], r["channel_id"],
            o["actual_ctr"], o["impressions"])


async def _insert_delivery_data(pool, rows: list[dict]):
    for r in rows:
        f = r["features"]
        o = r["outcome"]
        await pool.execute("""
            INSERT INTO delivery_features (content_id, channel_id,
                upload_hour_utc, upload_day_of_week,
                title_word_count, title_has_number, title_has_question,
                title_power_words, description_length, tag_count,
                seo_score, keyword_density,
                first_hour_views, first_day_views)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,0.0,$12,$13)
            ON CONFLICT DO NOTHING
        """, r["content_id"], r["channel_id"],
            f["upload_hour_utc"], f["upload_day_of_week"],
            f["title_word_count"], f["title_has_number"], f["title_has_question"],
            f["title_power_words"], f["description_length"], f["tag_count"],
            f["seo_score"], o["first_hour_views"], o["first_day_views"])


async def _insert_feedback_data(pool, rows: list[dict]):
    for r in rows:
        await pool.execute("""
            INSERT INTO feedback_loop (video_id, channel_id, title,
                idea_score, script_score, thumbnail_score, hook_retention_score,
                final_score, yt_views, yt_likes, yt_comments,
                engagement_rate, performance_tier, content_mode, status, yt_video_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'synthetic',$15)
            ON CONFLICT (video_id) DO NOTHING
        """, r["content_id"], r["channel_id"], r["title"],
            r["idea_score"], r["script_score"], r["thumbnail_score"],
            r["hook_retention_score"], r["final_score"],
            r["yt_views"], r["yt_likes"], r["yt_comments"],
            r["engagement_rate"], r["performance_tier"], r["content_mode"],
            f"SYN_{r['content_id']}")


# Main

async def generate(niches: list[str], count: int):
    pool = await get_pool()
    total = {"voice": 0, "thumbnail": 0, "delivery": 0, "feedback": 0}

    for niche in niches:
        profile = NICHE_PROFILES.get(niche, NICHE_PROFILES["tech"])
        channel_id = f"CH_synth_{niche}"

        # Ensure synthetic channel exists
        await pool.execute("""
            INSERT INTO channels (channel_id, channel_name, niche, content_mode, status)
            VALUES ($1, $2, $3, 'short', 'active')
            ON CONFLICT (channel_id) DO NOTHING
        """, channel_id, f"Synthetic {niche.title()} Channel", niche)

        voice_rows = [_gen_voice_row(i, niche, profile, channel_id) for i in range(count)]
        thumb_rows = [_gen_thumbnail_row(i, niche, profile, channel_id) for i in range(count)]
        deliv_rows = [_gen_delivery_row(i, niche, profile, channel_id) for i in range(count)]
        fb_rows = [_gen_feedback_row(i, niche, profile, channel_id) for i in range(count)]

        await _insert_voice_data(pool, voice_rows)
        await _insert_thumbnail_data(pool, thumb_rows)
        await _insert_delivery_data(pool, deliv_rows)
        await _insert_feedback_data(pool, fb_rows)

        total["voice"] += len(voice_rows)
        total["thumbnail"] += len(thumb_rows)
        total["delivery"] += len(deliv_rows)
        total["feedback"] += len(fb_rows)

        print(f"  ✓ {niche}: {count} rows per table")

    await close_pool()
    print(f"\nDone. Inserted: {total}")
    print("Run /train endpoints on each service to build models.")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--niches", default="tech,health,finance",
                        help="Comma-separated niche list (default: tech,health,finance)")
    parser.add_argument("--count", type=int, default=60,
                        help="Rows per niche per table (default: 60)")
    args = parser.parse_args()

    niches = [n.strip() for n in args.niches.split(",")]
    print(f"Generating {args.count} synthetic rows per niche for: {niches}")
    asyncio.run(generate(niches, args.count))


if __name__ == "__main__":
    main()
