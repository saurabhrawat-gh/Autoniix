from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

from src.services.analytics.pattern_miner import (
    mine_performance_patterns,
    get_channel_insights,
)
from src.observability.metrics import instrument_app

logger = structlog.get_logger()



class AnalyticsCollectRequest(BaseModel):
    channel_id: str
    youtube_video_ids: list[str] = Field(default_factory=list)


class PerformanceRequest(BaseModel):
    channel_id: str


class FeedbackLoopRequest(BaseModel):
    channel_id: str
    min_age_hours: int = 48


class TrendRefreshRequest(BaseModel):
    channel_id: str
    niche: str = ""



def _classify_tier(views: int, likes: int, comments: int) -> str:
    """Classify video performance tier: S/A/B/C/D."""
    engagement = (likes + comments * 2) / max(views, 1) * 100
    if views >= 100000 and engagement >= 8:
        return "S"
    elif views >= 50000 and engagement >= 5:
        return "A"
    elif views >= 10000 and engagement >= 3:
        return "B"
    elif views >= 1000:
        return "C"
    return "D"



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("analytics.starting")
    yield
    await close_pool()
    logger.info("analytics.stopped")


from src.observability.sentry import init_sentry
init_sentry("analytics")

app = FastAPI(title="Analytics Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="analytics")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="analytics")


@app.post("/collect", response_model=ServiceResponse)
async def collect(req: AnalyticsCollectRequest):
    """Collect YouTube analytics for published videos (views, likes, comments)."""
    logger.info("analytics.collecting", channel_id=req.channel_id, videos=len(req.youtube_video_ids))

    youtube_api_key = settings.youtube_api_key
    if not youtube_api_key:
        return ServiceResponse(status="skipped", data={"reason": "No YouTube API key configured"})

    analytics = []

    for video_id in req.youtube_video_ids:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "statistics,snippet,contentDetails",
                        "id": video_id,
                        "key": youtube_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if items:
                item = items[0]
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))

                tier = _classify_tier(views, likes, comments)
                engagement = (likes + comments * 2) / max(views, 1) * 100

                entry = {
                    "youtube_video_id": video_id,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "engagement_rate": round(engagement, 2),
                    "performance_tier": tier,
                    "title": item.get("snippet", {}).get("title", ""),
                }
                analytics.append(entry)

                try:
                    pool = await get_pool()
                    await pool.execute(
                        "UPDATE feedback_loop SET yt_views = $1, yt_likes = $2, yt_comments = $3, "
                        "engagement_rate = $4, performance_tier = $5, analytics_status = 'collected', "
                        "updated_at = NOW() WHERE yt_video_id = $6",
                        views, likes, comments, round(engagement, 2), tier, video_id)
                except Exception as db_err:
                    logger.warning("analytics.feedback_update_failed", video_id=video_id, error=str(db_err))

        except Exception as exc:
            logger.warning("analytics.video_failed", video_id=video_id, error=str(exc))
            analytics.append({"youtube_video_id": video_id, "error": str(exc)})

    if analytics:
        try:
            pool = await get_pool()
            valid = [a for a in analytics if "views" in a]
            total_views = sum(a["views"] for a in valid)
            total_likes = sum(a["likes"] for a in valid)
            avg_views = total_views / max(len(valid), 1)
            avg_engagement = sum(a.get("engagement_rate", 0) for a in valid) / max(len(valid), 1)
            tier_dist = {}
            for a in valid:
                t = a.get("performance_tier", "D")
                tier_dist[t] = tier_dist.get(t, 0) + 1

            perf = {
                "last_collected": datetime.utcnow().isoformat(),
                "total_views": total_views,
                "total_likes": total_likes,
                "video_count": len(valid),
                "avg_views": round(avg_views),
                "avg_engagement_rate": round(avg_engagement, 2),
                "tier_distribution": tier_dist,
            }
            await pool.execute(
                "UPDATE channels SET performance_memory = $1, updated_at = NOW() WHERE channel_id = $2",
                json.dumps(perf), req.channel_id)

            await pool.execute(
                "INSERT INTO performance_memory (channel_id, metric_type, metric_key, metric_value, period_start, period_end) "
                "VALUES ($1, 'aggregate', 'avg_views', $2, NOW() - INTERVAL '30 days', NOW()) "
                "ON CONFLICT (channel_id, metric_type, metric_key, period_start) DO UPDATE SET metric_value = $2, updated_at = NOW()",
                req.channel_id, avg_views)

        except Exception as e:
            logger.warning("analytics.db_update_failed", error=str(e))

    logger.info("analytics.collected", videos=len(analytics),
                 total_views=sum(a.get("views", 0) for a in analytics if "views" in a))

    return ServiceResponse(
        status="success",
        data={"analytics": analytics, "collected_count": len(analytics)},
    )


@app.post("/feedback-loop", response_model=ServiceResponse)
async def run_feedback_loop(req: FeedbackLoopRequest):
    """Populate feedback_loop for recently delivered videos, classify performance tiers."""
    logger.info("analytics.feedback_loop", channel_id=req.channel_id)

    try:
        pool = await get_pool()

        cutoff = datetime.utcnow() - timedelta(hours=req.min_age_hours)
        rows = await pool.fetch(
            "SELECT content_id, youtube_video_id, title, idea_score, "
            "script_structure_score, thumbnail_score, hook_retention_score, "
            "final_composite_score, content_mode "
            "FROM videos WHERE channel_id = $1 AND status = 'delivered' "
            "AND youtube_video_id IS NOT NULL AND created_at < $2 "
            "ORDER BY created_at DESC LIMIT 50",
            req.channel_id, cutoff)

        inserted = 0
        video_ids = []
        for row in rows:
            yt_id = row["youtube_video_id"]
            video_ids.append(yt_id)

            await pool.execute(
                "INSERT INTO feedback_loop (video_id, channel_id, title, idea_score, script_score, "
                "thumbnail_score, hook_retention_score, final_score, content_mode, status, yt_video_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', $10) "
                "ON CONFLICT (video_id) DO NOTHING",
                row["content_id"], req.channel_id, row["title"],
                row.get("idea_score"), row.get("script_structure_score"),
                row.get("thumbnail_score"), row.get("hook_retention_score"),
                row.get("final_composite_score"), row.get("content_mode"), yt_id)
            inserted += 1

        if video_ids:
            collect_result = await collect(AnalyticsCollectRequest(
                channel_id=req.channel_id, youtube_video_ids=video_ids))

        logger.info("analytics.feedback_loop_done", inserted=inserted, collected=len(video_ids))
        return ServiceResponse(
            status="success",
            data={"videos_processed": inserted, "video_ids_collected": video_ids},
        )

    except Exception as exc:
        logger.error("analytics.feedback_loop_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/performance", response_model=ServiceResponse)
async def get_performance(req: PerformanceRequest):
    """Get stored performance data for a channel with tier analysis."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT performance_memory, channel_name, niche FROM channels WHERE channel_id = $1",
            req.channel_id)
        if not row:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        top_videos = await pool.fetch(
            "SELECT title, yt_video_id, yt_views, yt_likes, engagement_rate, performance_tier, "
            "idea_score, script_score, thumbnail_score "
            "FROM feedback_loop WHERE channel_id = $1 AND performance_tier IN ('S', 'A') "
            "ORDER BY yt_views DESC LIMIT 10",
            req.channel_id)

        worst_videos = await pool.fetch(
            "SELECT title, yt_video_id, yt_views, engagement_rate, performance_tier "
            "FROM feedback_loop WHERE channel_id = $1 AND performance_tier IN ('D') "
            "ORDER BY yt_views ASC LIMIT 5",
            req.channel_id)

        perf_data = json.loads(row["performance_memory"]) if row["performance_memory"] else {}

        return ServiceResponse(
            status="success",
            data={
                "channel_id": req.channel_id,
                "channel_name": row["channel_name"],
                "niche": row["niche"],
                "performance": perf_data,
                "top_performers": [dict(r) for r in top_videos],
                "worst_performers": [dict(r) for r in worst_videos],
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/refresh-trends", response_model=ServiceResponse)
async def refresh_trends(req: TrendRefreshRequest):
    """Refresh trend intelligence for a channel's niche."""
    logger.info("analytics.refresh_trends", channel_id=req.channel_id)

    try:
        pool = await get_pool()

        if not req.niche:
            row = await pool.fetchrow(
                "SELECT niche FROM channels WHERE channel_id = $1", req.channel_id)
            niche = row["niche"] if row else "general"
        else:
            niche = req.niche

        youtube_api_key = settings.youtube_api_key
        trends = []

        if youtube_api_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://www.googleapis.com/youtube/v3/search",
                        params={
                            "part": "snippet",
                            "q": niche,
                            "type": "video",
                            "order": "viewCount",
                            "publishedAfter": (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z",
                            "maxResults": 10,
                            "key": youtube_api_key,
                        })
                    resp.raise_for_status()
                    items = resp.json().get("items", [])

                    for item in items:
                        vid_id = item.get("id", {}).get("videoId", "")
                        if not vid_id:
                            continue
                        trends.append({
                            "trend_type": "youtube_trending",
                            "trend_title": item["snippet"]["title"],
                            "source": "youtube",
                            "source_url": f"https://youtube.com/watch?v={vid_id}",
                            "channel": item["snippet"]["channelTitle"],
                        })
            except Exception as yt_err:
                logger.warning("analytics.youtube_trends_failed", error=str(yt_err))

        inserted = 0
        for trend in trends:
            try:
                await pool.execute(
                    "INSERT INTO trend_intelligence (channel_id, niche, trend_type, trend_title, "
                    "source, source_url, relevance_score, status) "
                    "VALUES ($1, $2, $3, $4, $5, $6, 7.0, 'active') "
                    "ON CONFLICT DO NOTHING",
                    req.channel_id, niche, trend["trend_type"], trend["trend_title"],
                    trend["source"], trend["source_url"])
                inserted += 1
            except Exception:
                pass

        logger.info("analytics.trends_refreshed", niche=niche, trends=len(trends), inserted=inserted)
        return ServiceResponse(
            status="success",
            data={"niche": niche, "trends_found": len(trends), "trends_inserted": inserted},
        )

    except Exception as exc:
        logger.error("analytics.refresh_trends_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))



@app.post("/mine-patterns", response_model=ServiceResponse)
async def mine_patterns(req: PerformanceRequest):
    """Discover performance patterns from historical video data."""
    try:
        channel = await _load_channel(req.channel_id)
        niche = channel.get("niche", "general")
        result = await mine_performance_patterns(req.channel_id, niche)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/insights/{channel_id}", response_model=ServiceResponse)
async def insights(channel_id: str):
    """Get stored performance insights for a channel."""
    try:
        result = await get_channel_insights(channel_id)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


if __name__ == "__main__":
    uvicorn.run("src.services.analytics.main:app", host="0.0.0.0", port=8008, log_level="info")
