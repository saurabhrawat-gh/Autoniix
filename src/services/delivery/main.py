from __future__ import annotations

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


class DeliveryRequest(BaseModel):
    content_id: str
    channel_id: str
    content_mode: str = "short"
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    video_url: str  # URL to rendered video in MinIO
    thumbnail_url: str = ""  # URL to thumbnail in MinIO
    privacy_status: str = "private"  # private|unlisted|public
    category_id: str = "22"  # 22 = People & Blogs, 27 = Education, 26 = How-to
    is_short: bool = False
    scheduled_at: str = ""  # ISO datetime for scheduled publish
    quality_scores: dict = Field(default_factory=dict)
    human_review_required: bool = False


class HumanReviewRequest(BaseModel):
    content_id: str
    approved: bool
    reviewer: str = "admin"
    notes: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("delivery.starting")
    yield
    await close_pool()
    logger.info("delivery.stopped")


app = FastAPI(title="Delivery Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="delivery")


async def refresh_access_token() -> str:
    """Get a fresh access token using the refresh token."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_oauth_client_id if hasattr(settings, 'google_oauth_client_id') else "",
                "client_secret": settings.google_oauth_client_secret if hasattr(settings, 'google_oauth_client_secret') else "",
                "refresh_token": settings.google_oauth_refresh_token if hasattr(settings, 'google_oauth_refresh_token') else "",
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _compute_final_score(scores: dict) -> float:
    """Weighted composite: research 15% + script 25% + hook 15% + voice 10% + thumbnail 15% + direction 10% + production 10%."""
    weights = {
        "research_depth_score": 0.15,
        "script_structure_score": 0.25,
        "hook_retention_score": 0.15,
        "voice_quality_score": 0.10,
        "thumbnail_score": 0.15,
        "direction_score": 0.10,
        "production_score": 0.10,
    }
    total = 0.0
    for key, weight in weights.items():
        total += float(scores.get(key, 7.0)) * weight
    return round(total, 2)


@app.post("/human-review", response_model=ServiceResponse)
async def human_review(req: HumanReviewRequest):
    """Submit human review decision for a content piece."""
    logger.info("delivery.human_review", content_id=req.content_id, approved=req.approved)

    try:
        pool = await get_pool()
        status = "approved" if req.approved else "rejected"
        await pool.execute(
            "UPDATE videos SET human_review_status = $1, human_review_notes = $2, "
            "human_reviewer = $3, status = $4, updated_at = NOW() WHERE content_id = $5",
            status, req.notes, req.reviewer,
            "ready_to_deliver" if req.approved else "rejected",
            req.content_id)

        return ServiceResponse(
            status="success",
            data={"content_id": req.content_id, "review_status": status, "reviewer": req.reviewer},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload", response_model=ServiceResponse)
async def upload(req: DeliveryRequest):
    logger.info("delivery.uploading", content_id=req.content_id, title=req.title[:50])

    try:
        # ── Pre-flight: Compute final composite score ────
        final_score = _compute_final_score(req.quality_scores)
        logger.info("delivery.final_score", score=final_score)

        # ── Human review gate ────────────────────────────
        if req.human_review_required:
            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT human_review_status FROM videos WHERE content_id = $1", req.content_id)
            if not row or row["human_review_status"] != "approved":
                # Mark as pending review instead of uploading
                await pool.execute(
                    "UPDATE videos SET status = 'pending_review', final_composite_score = $1, "
                    "updated_at = NOW() WHERE content_id = $2",
                    final_score, req.content_id)
                return ServiceResponse(
                    status="pending_review",
                    data={
                        "content_id": req.content_id,
                        "final_score": final_score,
                        "message": "Queued for human review before delivery",
                    },
                )

        # Step 1: Get fresh access token
        access_token = await refresh_access_token()

        # Step 2: Download video from MinIO
        async with httpx.AsyncClient(timeout=300.0) as client:
            video_resp = await client.get(req.video_url)
            video_resp.raise_for_status()
            video_bytes = video_resp.content

        # Step 3: Upload to YouTube via resumable upload
        # Create the video resource
        metadata = {
            "snippet": {
                "title": req.title[:100],
                "description": req.description[:5000],
                "tags": req.tags[:30],
                "categoryId": req.category_id,
            },
            "status": {
                "privacyStatus": req.privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Initiate resumable upload
            init_resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos"
                "?uploadType=resumable&part=snippet,status",
                headers={**headers, "Content-Type": "application/json"},
                json=metadata,
            )
            init_resp.raise_for_status()
            upload_url = init_resp.headers.get("Location", "")

            if not upload_url:
                raise HTTPException(status_code=500, detail="No upload URL returned from YouTube")

            # Upload the video bytes
            upload_resp = await client.put(
                upload_url,
                headers={"Content-Type": "video/mp4"},
                content=video_bytes,
            )
            upload_resp.raise_for_status()
            yt_data = upload_resp.json()

        youtube_video_id = yt_data.get("id", "")

        # Step 4: Upload thumbnail (if provided)
        if req.thumbnail_url and youtube_video_id:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    thumb_resp = await client.get(req.thumbnail_url)
                    thumb_resp.raise_for_status()
                    thumb_bytes = thumb_resp.content

                    await client.post(
                        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
                        f"?videoId={youtube_video_id}",
                        headers={**headers, "Content-Type": "image/png"},
                        content=thumb_bytes,
                    )
            except Exception as thumb_err:
                logger.warning("delivery.thumbnail_upload_failed", error=str(thumb_err))

        # Step 5: Log to DB + create feedback_loop entry
        import json as json_mod
        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET youtube_video_id = $1, delivery_result = $2, "
                "final_composite_score = $3, status = 'delivered', updated_at = NOW() "
                "WHERE content_id = $4",
                youtube_video_id,
                json_mod.dumps({
                    "youtube_video_id": youtube_video_id,
                    "privacy_status": req.privacy_status,
                    "url": f"https://youtu.be/{youtube_video_id}",
                    "is_short": req.is_short,
                }),
                final_score,
                req.content_id,
            )

            # Create feedback_loop entry for future analytics collection
            scores = req.quality_scores
            await pool.execute(
                "INSERT INTO feedback_loop (video_id, channel_id, title, idea_score, script_score, "
                "thumbnail_score, hook_retention_score, final_score, content_mode, status, yt_video_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'delivered', $10) "
                "ON CONFLICT (video_id) DO UPDATE SET yt_video_id = $10, status = 'delivered', updated_at = NOW()",
                req.content_id, req.channel_id, req.title,
                float(scores.get("idea_score", 0)),
                float(scores.get("script_structure_score", 0)),
                float(scores.get("thumbnail_score", 0)),
                float(scores.get("hook_retention_score", 0)),
                final_score, req.content_mode, youtube_video_id)

        except Exception as e:
            logger.warning("delivery.db_log_failed", error=str(e))

        logger.info("delivery.uploaded", youtube_video_id=youtube_video_id)

        return ServiceResponse(
            status="success",
            data={
                "youtube_video_id": youtube_video_id,
                "youtube_url": f"https://youtu.be/{youtube_video_id}",
                "privacy_status": req.privacy_status,
            },
            cost={"cost_usd": 0, "provider": "youtube"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delivery.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.delivery.main:app", host="0.0.0.0", port=8007, log_level="info")
