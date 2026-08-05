"""Trend Collector — Google Trends (pytrends) + YouTube Data API signals.

Collects momentum, rising queries, and volume data for a niche/keyword set.
Stores snapshots in `trend_signals` table for downstream scoring.
All external calls are free-tier safe with caching and backoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta

import httpx
import structlog

from core.config import settings
from core.db import get_pool
from core.redis_client import get_redis

logger = structlog.get_logger()

CACHE_TTL = 3600 * 6


async def _fetch_google_trends(keywords: list[str], timeframe: str = "now 7-d") -> dict:
    """Fetch Google Trends interest-over-time and related queries.
    Runs pytrends in a thread to avoid blocking the event loop.
    """

    def _sync_fetch():
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl="en-US", tz=330, timeout=(10, 25), retries=2)
            kws = keywords[:5]
            pytrends.build_payload(kws, cat=0, timeframe=timeframe, geo="", gprop="youtube")

            iot = pytrends.interest_over_time()
            momentum = {}
            if not iot.empty:
                for kw in kws:
                    if kw in iot.columns:
                        vals = iot[kw].tolist()
                        recent = vals[-3:] if len(vals) >= 3 else vals
                        older = vals[:3] if len(vals) >= 3 else vals
                        avg_recent = sum(recent) / max(len(recent), 1)
                        avg_older = sum(older) / max(len(older), 1)
                        momentum[kw] = {
                            "current_index": int(vals[-1]) if vals else 0,
                            "avg_recent": round(avg_recent, 1),
                            "avg_older": round(avg_older, 1),
                            "momentum": round((avg_recent - avg_older) / max(avg_older, 1), 3),
                        }

            related = {}
            try:
                rq = pytrends.related_queries()
                for kw in kws:
                    if kw in rq:
                        top = rq[kw].get("top")
                        rising = rq[kw].get("rising")
                        related[kw] = {
                            "top": top.head(10).to_dict("records") if top is not None and not top.empty else [],
                            "rising": rising.head(10).to_dict("records")
                            if rising is not None and not rising.empty
                            else [],
                        }
            except Exception:
                pass

            suggestions = {}
            for kw in kws[:3]:
                try:
                    sugg = pytrends.suggestions(keyword=kw)
                    suggestions[kw] = [s.get("title", "") for s in sugg[:5]]
                except Exception:
                    suggestions[kw] = []

            return {"momentum": momentum, "related": related, "suggestions": suggestions}
        except Exception as e:
            logger.warning("trend_collector.pytrends_failed", error=str(e))
            return {"momentum": {}, "related": {}, "suggestions": {}}

    return await asyncio.to_thread(_sync_fetch)


async def _fetch_youtube_suggestions(keyword: str) -> list[str]:
    """Fetch YouTube search autocomplete suggestions (free, no API key)."""
    cache_key = f"yt_suggest:{hashlib.md5(keyword.encode()).hexdigest()}"
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://suggestqueries-clients6.youtube.com/complete/search",
                params={"client": "youtube", "q": keyword, "ds": "yt"},
            )
            resp.raise_for_status()
            text = resp.text
            start = text.index("(") + 1
            end = text.rindex(")")
            data = json.loads(text[start:end])
            suggestions = [item[0] for item in data[1]] if len(data) > 1 else []
            await redis.set(cache_key, json.dumps(suggestions), ex=CACHE_TTL)
            return suggestions
    except Exception as e:
        logger.warning("trend_collector.yt_suggest_failed", error=str(e))
        return []


async def _fetch_youtube_trending_videos(niche: str, max_results: int = 15) -> list[dict]:
    """Fetch recent popular videos in a niche via YouTube Data API."""
    api_key = settings.youtube_api_key
    if not api_key:
        return []

    cache_key = f"yt_trending:{hashlib.md5(niche.encode()).hexdigest()}"
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": niche,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "maxResults": max_results,
                    "key": api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            video_ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
            stats = {}
            if video_ids:
                stats_resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "statistics,contentDetails",
                        "id": ",".join(video_ids),
                        "key": api_key,
                    },
                )
                stats_resp.raise_for_status()
                for v in stats_resp.json().get("items", []):
                    stats[v["id"]] = {
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "likes": int(v["statistics"].get("likeCount", 0)),
                        "comments": int(v["statistics"].get("commentCount", 0)),
                    }

            results = []
            for it in items:
                vid = it.get("id", {}).get("videoId", "")
                results.append(
                    {
                        "video_id": vid,
                        "title": it["snippet"]["title"],
                        "channel": it["snippet"]["channelTitle"],
                        "published": it["snippet"]["publishedAt"],
                        **stats.get(vid, {}),
                    }
                )

            await redis.set(cache_key, json.dumps(results), ex=CACHE_TTL)
            return results
    except Exception as e:
        logger.warning("trend_collector.yt_trending_failed", error=str(e))
        return []


async def _store_trend_signals(niche: str, trends_data: dict) -> int:
    """Persist trend signals to DB for downstream scoring."""
    pool = await get_pool()
    stored = 0
    today = date.today()

    momentum = trends_data.get("momentum", {})
    related = trends_data.get("related", {})

    for keyword, m_data in momentum.items():
        rising = related.get(keyword, {}).get("rising", [])
        top = related.get(keyword, {}).get("top", [])

        try:
            await pool.execute(
                """
                INSERT INTO trend_signals (niche, keyword, source, signal_type,
                    momentum_score, volume_index, related_queries, rising_queries,
                    snapshot_date, raw_data)
                VALUES ($1, $2, 'google_trends', 'momentum',
                    $3, $4, $5, $6, $7, $8)
                ON CONFLICT (niche, keyword, source, snapshot_date) DO UPDATE SET
                    momentum_score = EXCLUDED.momentum_score,
                    volume_index = EXCLUDED.volume_index,
                    related_queries = EXCLUDED.related_queries,
                    rising_queries = EXCLUDED.rising_queries,
                    raw_data = EXCLUDED.raw_data
            """,
                niche,
                keyword,
                float(m_data.get("momentum", 0)),
                int(m_data.get("current_index", 0)),
                json.dumps(top),
                json.dumps(rising),
                today,
                json.dumps(m_data),
            )
            stored += 1
        except Exception as e:
            logger.warning("trend_collector.store_failed", keyword=keyword, error=str(e))

    return stored


async def collect_trends(niche: str, keywords: list[str]) -> dict:
    """Main entry: collect all trend signals for a niche + keywords.

    Returns:
        dict with keys: google_trends, youtube_suggestions, youtube_trending, signals_stored
    """
    logger.info("trend_collector.start", niche=niche, keywords=keywords[:5])

    gt_task = _fetch_google_trends(keywords[:5])
    yt_suggest_tasks = [_fetch_youtube_suggestions(kw) for kw in keywords[:3]]
    yt_trending_task = _fetch_youtube_trending_videos(niche)

    gt_data, *yt_suggestions, yt_trending = await asyncio.gather(gt_task, *yt_suggest_tasks, yt_trending_task)

    all_suggestions = {}
    for i, kw in enumerate(keywords[:3]):
        if i < len(yt_suggestions):
            all_suggestions[kw] = yt_suggestions[i]

    stored = await _store_trend_signals(niche, gt_data)

    result = {
        "google_trends": gt_data,
        "youtube_suggestions": all_suggestions,
        "youtube_trending": yt_trending,
        "signals_stored": stored,
    }

    logger.info(
        "trend_collector.done",
        momentum_keywords=len(gt_data.get("momentum", {})),
        trending_videos=len(yt_trending),
        suggestions=sum(len(v) for v in all_suggestions.values()),
        stored=stored,
    )

    return result
