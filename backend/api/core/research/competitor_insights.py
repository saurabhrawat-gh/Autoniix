"""Competitor Insights — YouTube Data API channel/video analysis.

Tracks competitor channels per niche, identifies outlier videos
(small channels with viral hits), and computes view velocity.
All data stored in `competitor_channels` / `competitor_videos` tables.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import httpx
import structlog

from core.config import settings
from core.db import get_pool
from core.redis_client import get_redis

logger = structlog.get_logger()

CACHE_TTL = 3600 * 12



async def _yt_get(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API GET request with caching."""
    api_key = settings.youtube_api_key
    if not api_key:
        return {}
    params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://www.googleapis.com/youtube/v3/{endpoint}",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("competitor.yt_api_failed", endpoint=endpoint, error=str(e))
        return {}


async def _get_channel_stats(channel_ids: list[str]) -> dict[str, dict]:
    """Get stats for multiple channels in one batch."""
    if not channel_ids:
        return {}
    data = await _yt_get("channels", {
        "part": "statistics,snippet",
        "id": ",".join(channel_ids[:50]),
    })
    result = {}
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        result[item["id"]] = {
            "name": item.get("snippet", {}).get("title", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
        }
    return result


async def _get_recent_videos(channel_id: str, max_results: int = 20) -> list[dict]:
    """Get recent videos from a channel."""
    data = await _yt_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "order": "date",
        "maxResults": max_results,
        "publishedAfter": (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    video_ids = [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    stats_data = await _yt_get("videos", {
        "part": "statistics,contentDetails,snippet",
        "id": ",".join(video_ids),
    })

    results = []
    for v in stats_data.get("items", []):
        stats = v.get("statistics", {})
        snippet = v.get("snippet", {})
        dur_str = v.get("contentDetails", {}).get("duration", "PT0S")
        duration_s = _parse_iso_duration(dur_str)

        results.append({
            "video_id": v["id"],
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "tags": ",".join(snippet.get("tags", [])[:20]),
            "published_at": snippet.get("publishedAt", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration_seconds": duration_s,
        })
    return results


def _parse_iso_duration(dur: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not match:
        return 0
    h, m, s = (int(x) if x else 0 for x in match.groups())
    return h * 3600 + m * 60 + s



def detect_outliers(videos: list[dict], channel_avg_views: int) -> list[dict]:
    """Flag videos that significantly outperform the channel's average.

    An outlier = views >= 3x channel average (or 10x for small channels).
    """
    if not videos or channel_avg_views <= 0:
        return videos

    threshold = max(3.0, 10.0 if channel_avg_views < 5000 else 5.0)

    for v in videos:
        multiplier = v["views"] / max(channel_avg_views, 1)
        v["outlier_multiplier"] = round(multiplier, 2)
        v["is_outlier"] = multiplier >= threshold

    return videos


def compute_view_velocity(videos: list[dict]) -> list[dict]:
    """Estimate view velocity based on views/age for each video."""
    now = datetime.utcnow()
    for v in videos:
        try:
            pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            age_hours = max((now - pub).total_seconds() / 3600, 1)
            v["view_velocity_24h"] = int(v["views"] / age_hours * 24)
        except Exception:
            v["view_velocity_24h"] = 0
    return videos



async def _store_competitor_channel(our_channel_id: str, comp: dict) -> None:
    pool = await get_pool()
    try:
        await pool.execute("""
            INSERT INTO competitor_channels
                (channel_id, competitor_yt_id, competitor_name, niche,
                 subscriber_count, video_count, avg_views, last_scraped_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (channel_id, competitor_yt_id) DO UPDATE SET
                competitor_name = EXCLUDED.competitor_name,
                subscriber_count = EXCLUDED.subscriber_count,
                video_count = EXCLUDED.video_count,
                avg_views = EXCLUDED.avg_views,
                last_scraped_at = NOW()
        """,
            our_channel_id, comp["competitor_yt_id"], comp.get("name", ""),
            comp.get("niche", ""), comp.get("subscriber_count", 0),
            comp.get("video_count", 0), comp.get("avg_views", 0),
        )
    except Exception as e:
        logger.warning("competitor.store_channel_failed", error=str(e))


async def _store_competitor_videos(niche: str, videos: list[dict], competitor_yt_id: str) -> int:
    """Persist competitor videos with title embeddings (Phase 8).

    The schema has carried ``title_embedding vector(384)`` and an IVFFlat
    index since day one, but the column was never written. Phase 8's
    saturation scorer needs it populated so cosine queries can compare
    candidate topics against recent niche output.

    Embeddings are batch-encoded (one model invocation per call) before
    the row-level insert loop. A failure to compute embeddings is *not*
    fatal — we fall back to NULL so the rest of the row still lands and
    the scorer treats the video as "no embedding, skip" instead of
    breaking the pipeline.
    """
    if not videos:
        return 0

    pool = await get_pool()

    embeddings: list[list[float] | None] = [None] * len(videos)
    try:
        from services_api.research.similarity import compute_embeddings_batch
        titles = [(v.get("title") or "").strip() for v in videos]
        idx_with_text = [(i, t) for i, t in enumerate(titles) if t]
        if idx_with_text:
            non_empty = [t for _, t in idx_with_text]
            vecs = await compute_embeddings_batch(non_empty)
            for (orig_idx, _), vec in zip(idx_with_text, vecs):
                embeddings[orig_idx] = vec
    except Exception as exc:
        logger.warning("competitor.embed_batch_failed",
                       count=len(videos), error=str(exc))

    stored = 0
    for v, emb in zip(videos, embeddings):
        try:
            emb_param = (
                "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
                if emb is not None else None
            )
            await pool.execute("""
                INSERT INTO competitor_videos
                    (competitor_yt_id, video_yt_id, title, description, tags,
                     published_at, view_count, like_count, comment_count,
                     duration_seconds, view_velocity_24h, is_outlier,
                     outlier_multiplier, niche, title_embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                        $13, $14, $15::vector)
                ON CONFLICT (video_yt_id) DO UPDATE SET
                    view_count = EXCLUDED.view_count,
                    like_count = EXCLUDED.like_count,
                    comment_count = EXCLUDED.comment_count,
                    view_velocity_24h = EXCLUDED.view_velocity_24h,
                    is_outlier = EXCLUDED.is_outlier,
                    outlier_multiplier = EXCLUDED.outlier_multiplier,
                    -- Only overwrite the embedding if we computed one
                    -- this round; otherwise keep the existing vector
                    -- so a transient encode failure doesn't blank prior
                    -- good data.
                    title_embedding = COALESCE(EXCLUDED.title_embedding,
                                               competitor_videos.title_embedding),
                    updated_at = NOW()
            """,
                competitor_yt_id, v["video_id"], v["title"],
                v.get("description", ""), v.get("tags", ""),
                datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) if v.get("published_at") else None,
                v["views"], v["likes"], v["comments"],
                v.get("duration_seconds", 0), v.get("view_velocity_24h", 0),
                v.get("is_outlier", False), v.get("outlier_multiplier", 1.0),
                niche, emb_param,
            )
            stored += 1
        except Exception as e:
            logger.warning("competitor.store_video_failed", video=v.get("video_id"), error=str(e))
    return stored



async def _search_niche_outliers(niche: str) -> list[dict]:
    """Find viral videos in the niche from any channel (including small ones)."""
    api_key = settings.youtube_api_key
    if not api_key:
        return []

    data = await _yt_get("search", {
        "part": "snippet",
        "q": niche,
        "type": "video",
        "order": "viewCount",
        "publishedAfter": (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maxResults": 25,
    })

    video_ids = [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    stats_data = await _yt_get("videos", {
        "part": "statistics,snippet,contentDetails",
        "id": ",".join(video_ids),
    })

    channel_ids = list({v["snippet"]["channelId"] for v in stats_data.get("items", [])})
    channel_stats = await _get_channel_stats(channel_ids)

    outliers = []
    for v in stats_data.get("items", []):
        stats = v.get("statistics", {})
        ch_id = v["snippet"]["channelId"]
        ch = channel_stats.get(ch_id, {})
        views = int(stats.get("viewCount", 0))
        ch_avg = ch.get("view_count", 0) / max(ch.get("video_count", 1), 1)
        subs = ch.get("subscriber_count", 0)

        if subs < 50000 and views > ch_avg * 5:
            outliers.append({
                "video_id": v["id"],
                "title": v["snippet"]["title"],
                "channel": v["snippet"]["channelTitle"],
                "channel_id": ch_id,
                "views": views,
                "subs": subs,
                "multiplier": round(views / max(ch_avg, 1), 1),
            })

    outliers.sort(key=lambda x: x.get("multiplier", 0), reverse=True)
    return outliers[:10]



async def collect_competitor_insights(
    our_channel_id: str,
    niche: str,
    competitor_yt_ids: list[str] | None = None,
) -> dict:
    """Main entry: analyze competitors and find niche outliers.

    Args:
        our_channel_id: Our channel's DB ID (for linking).
        niche: The niche/sub-niche to search.
        competitor_yt_ids: Optional list of known competitor YouTube channel IDs.

    Returns:
        dict with competitor_stats, outlier_videos, niche_outliers, stored counts.
    """
    logger.info("competitor.start", niche=niche, competitors=len(competitor_yt_ids or []))

    if not competitor_yt_ids:
        search_data = await _yt_get("search", {
            "part": "snippet",
            "q": niche,
            "type": "channel",
            "order": "relevance",
            "maxResults": 10,
        })
        competitor_yt_ids = [
            it["snippet"]["channelId"]
            for it in search_data.get("items", [])
        ]

    channel_stats = await _get_channel_stats(competitor_yt_ids[:10])

    all_outliers = []
    total_stored = 0

    for comp_id in competitor_yt_ids[:5]:
        ch = channel_stats.get(comp_id, {})
        avg_views = ch.get("view_count", 0) / max(ch.get("video_count", 1), 1)

        videos = await _get_recent_videos(comp_id, max_results=15)
        videos = compute_view_velocity(videos)
        videos = detect_outliers(videos, int(avg_views))

        await _store_competitor_channel(our_channel_id, {
            "competitor_yt_id": comp_id,
            "name": ch.get("name", ""),
            "niche": niche,
            "subscriber_count": ch.get("subscriber_count", 0),
            "video_count": ch.get("video_count", 0),
            "avg_views": int(avg_views),
        })
        stored = await _store_competitor_videos(niche, videos, comp_id)
        total_stored += stored

        outlier_vids = [v for v in videos if v.get("is_outlier")]
        all_outliers.extend(outlier_vids)

    niche_outliers = await _search_niche_outliers(niche)

    all_outliers.sort(key=lambda x: x.get("outlier_multiplier", 0), reverse=True)

    result = {
        "competitor_count": len(channel_stats),
        "competitor_stats": {
            cid: {
                "name": ch.get("name", ""),
                "subs": ch.get("subscriber_count", 0),
                "videos": ch.get("video_count", 0),
                "avg_views": ch.get("view_count", 0) // max(ch.get("video_count", 1), 1),
            }
            for cid, ch in channel_stats.items()
        },
        "outlier_videos": all_outliers[:10],
        "niche_outliers": niche_outliers,
        "videos_stored": total_stored,
    }

    logger.info("competitor.done",
                competitors=len(channel_stats),
                outliers=len(all_outliers),
                niche_outliers=len(niche_outliers),
                stored=total_stored)

    return result
