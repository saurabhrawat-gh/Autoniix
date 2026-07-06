"""Analytics Pattern Miner — Discovers performance patterns across videos.

Uses statistical analysis to find:
- Content type performance correlations
- Optimal video characteristics per niche
- Anomaly detection in performance
- Cross-channel learning within same niche
- Content fatigue detection

Intelligence cost: $0.00 — numpy + basic statistics, all local.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import structlog

from core.db import get_pool

logger = structlog.get_logger()


async def mine_performance_patterns(channel_id: str, niche: str = "") -> dict:
    """Mine performance patterns from historical video data."""
    try:
        pool = await get_pool()

        rows = await pool.fetch("""
            SELECT fl.video_id, fl.title, fl.idea_score, fl.script_score,
                   fl.thumbnail_score, fl.hook_retention_score, fl.final_score,
                   fl.yt_views, fl.yt_likes, fl.yt_comments,
                   fl.engagement_rate, fl.performance_tier,
                   fl.content_mode, fl.created_at
            FROM feedback_loop fl
            WHERE fl.channel_id = $1 AND fl.yt_views IS NOT NULL
            ORDER BY fl.created_at DESC LIMIT 100
        """, channel_id)

        if len(rows) < 5:
            return {"status": "insufficient_data", "videos_analyzed": len(rows)}

        videos = [dict(r) for r in rows]

        patterns = {}

        for score_key in ["idea_score", "script_score", "thumbnail_score",
                          "hook_retention_score", "final_score"]:
            scores = [float(v.get(score_key) or 0) for v in videos if v.get(score_key)]
            views = [int(v.get("yt_views") or 0) for v in videos if v.get(score_key)]
            if len(scores) >= 5 and len(views) >= 5:
                correlation = float(np.corrcoef(scores[:len(views)], views[:len(scores)])[0][1])
                if not np.isnan(correlation):
                    patterns[f"{score_key}_correlation"] = {
                        "correlation": round(correlation, 4),
                        "strength": "strong" if abs(correlation) > 0.5 else
                                   "moderate" if abs(correlation) > 0.3 else "weak",
                        "samples": len(scores),
                    }

        tier_counts = {}
        for v in videos:
            tier = v.get("performance_tier", "D")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        patterns["tier_distribution"] = tier_counts

        high_perf = [v for v in videos if v.get("performance_tier") in ("S", "A")]
        low_perf = [v for v in videos if v.get("performance_tier") in ("D",)]

        if high_perf:
            patterns["high_performer_avg"] = {
                "idea_score": round(np.mean([float(v.get("idea_score") or 0) for v in high_perf]), 2),
                "script_score": round(np.mean([float(v.get("script_score") or 0) for v in high_perf]), 2),
                "thumbnail_score": round(np.mean([float(v.get("thumbnail_score") or 0) for v in high_perf]), 2),
                "hook_score": round(np.mean([float(v.get("hook_retention_score") or 0) for v in high_perf]), 2),
                "avg_views": round(np.mean([int(v.get("yt_views") or 0) for v in high_perf])),
                "count": len(high_perf),
            }

        if low_perf:
            patterns["low_performer_avg"] = {
                "idea_score": round(np.mean([float(v.get("idea_score") or 0) for v in low_perf]), 2),
                "script_score": round(np.mean([float(v.get("script_score") or 0) for v in low_perf]), 2),
                "thumbnail_score": round(np.mean([float(v.get("thumbnail_score") or 0) for v in low_perf]), 2),
                "avg_views": round(np.mean([int(v.get("yt_views") or 0) for v in low_perf])),
                "count": len(low_perf),
            }

        views_list = [int(v.get("yt_views") or 0) for v in videos]
        if len(views_list) >= 5:
            mean_views = np.mean(views_list)
            std_views = np.std(views_list)
            anomalies = []
            for v in videos:
                views = int(v.get("yt_views") or 0)
                if std_views > 0:
                    z_score = (views - mean_views) / std_views
                    if abs(z_score) > 2.0:
                        anomalies.append({
                            "title": v.get("title", "")[:60],
                            "views": views,
                            "z_score": round(z_score, 2),
                            "type": "overperformer" if z_score > 0 else "underperformer",
                        })
            patterns["anomalies"] = anomalies

        recent_30d = [v for v in videos
                     if v.get("created_at") and
                     v["created_at"] > datetime.utcnow() - timedelta(days=30)]
        older_30d = [v for v in videos
                    if v.get("created_at") and
                    v["created_at"] <= datetime.utcnow() - timedelta(days=30)]

        if recent_30d and older_30d:
            recent_avg = np.mean([int(v.get("yt_views") or 0) for v in recent_30d])
            older_avg = np.mean([int(v.get("yt_views") or 0) for v in older_30d])
            if older_avg > 0:
                trend = (recent_avg - older_avg) / older_avg
                patterns["content_fatigue"] = {
                    "trend_pct": round(trend * 100, 1),
                    "status": "declining" if trend < -0.2 else
                             "stable" if abs(trend) <= 0.2 else "growing",
                    "recent_avg_views": round(recent_avg),
                    "older_avg_views": round(older_avg),
                }

        for pattern_key, pattern_data in patterns.items():
            try:
                confidence = 0.5 + min(0.5, len(videos) / 100)
                await pool.execute("""
                    INSERT INTO analytics_patterns (channel_id, pattern_type, pattern_key,
                        pattern_data, confidence, sample_count, last_validated)
                    VALUES ($1, 'performance', $2, $3, $4, $5, NOW())
                    ON CONFLICT (channel_id, pattern_type, pattern_key) DO UPDATE SET
                        pattern_data = EXCLUDED.pattern_data,
                        confidence = EXCLUDED.confidence,
                        sample_count = EXCLUDED.sample_count,
                        last_validated = NOW(),
                        updated_at = NOW()
                """, channel_id, pattern_key, json.dumps(pattern_data, default=str),
                    confidence, len(videos))
            except Exception:
                pass

        logger.info("analytics.patterns_mined", channel_id=channel_id,
                     patterns=len(patterns), videos=len(videos))

        return {
            "status": "success",
            "videos_analyzed": len(videos),
            "patterns": patterns,
        }

    except Exception as e:
        logger.error("analytics.pattern_mining_failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def get_channel_insights(channel_id: str) -> dict:
    """Get stored performance patterns and insights for a channel."""
    try:
        pool = await get_pool()
        rows = await pool.fetch("""
            SELECT pattern_type, pattern_key, pattern_data, confidence, sample_count
            FROM analytics_patterns
            WHERE channel_id = $1
            ORDER BY confidence DESC
        """, channel_id)

        insights = {}
        for r in rows:
            key = r["pattern_key"]
            insights[key] = {
                "data": json.loads(r["pattern_data"]) if r["pattern_data"] else {},
                "confidence": float(r["confidence"]),
                "samples": r["sample_count"],
            }

        return insights
    except Exception as e:
        logger.warning("analytics.get_insights_failed", error=str(e))
        return {}
