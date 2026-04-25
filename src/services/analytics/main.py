from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

logger = structlog.get_logger()


class AnalyticsCollectRequest(BaseModel):
    channel_id: str
    youtube_video_ids: list[str] = Field(default_factory=list)


class PerformanceRequest(BaseModel):
    channel_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("analytics.starting")
    yield
    await close_pool()
    logger.info("analytics.stopped")


app = FastAPI(title="Analytics Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="analytics")


@app.post("/collect", response_model=ServiceResponse)
async def collect(req: AnalyticsCollectRequest):
    """Collect YouTube analytics for published videos."""
    logger.info("analytics.collecting", channel_id=req.channel_id, videos=len(req.youtube_video_ids))

    youtube_api_key = settings.youtube_api_key if hasattr(settings, "youtube_api_key") else ""
    if not youtube_api_key:
        return ServiceResponse(status="skipped", data={"reason": "No YouTube API key configured"})

    analytics = []

    for video_id in req.youtube_video_ids:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "statistics,snippet",
                        "id": video_id,
                        "key": youtube_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                analytics.append({
                    "youtube_video_id": video_id,
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "favorites": int(stats.get("favoriteCount", 0)),
                })

        except Exception as exc:
            logger.warning("analytics.video_failed", video_id=video_id, error=str(exc))
            analytics.append({"youtube_video_id": video_id, "error": str(exc)})

    # Update performance_memory for the channel
    if analytics:
        try:
            pool = await get_pool()
            total_views = sum(a.get("views", 0) for a in analytics if "views" in a)
            total_likes = sum(a.get("likes", 0) for a in analytics if "likes" in a)
            perf = {
                "last_collected": __import__("datetime").datetime.utcnow().isoformat(),
                "total_views": total_views,
                "total_likes": total_likes,
                "video_count": len([a for a in analytics if "views" in a]),
            }
            await pool.execute(
                "UPDATE channels SET performance_memory = $1, updated_at = NOW() WHERE channel_id = $2",
                json.dumps(perf),
                req.channel_id,
            )
        except Exception as e:
            logger.warning("analytics.db_update_failed", error=str(e))

    logger.info("analytics.collected", videos=len(analytics))

    return ServiceResponse(
        status="success",
        data={"analytics": analytics, "collected_count": len(analytics)},
    )


@app.post("/performance", response_model=ServiceResponse)
async def get_performance(req: PerformanceRequest):
    """Get stored performance data for a channel."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT performance_memory, channel_name, niche FROM channels WHERE channel_id = $1",
            req.channel_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        return ServiceResponse(
            status="success",
            data={
                "channel_id": req.channel_id,
                "channel_name": row["channel_name"],
                "niche": row["niche"],
                "performance": json.loads(row["performance_memory"]) if row["performance_memory"] else {},
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.analytics.main:app", host="0.0.0.0", port=8008, log_level="info")
