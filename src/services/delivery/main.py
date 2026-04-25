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
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    video_url: str  # URL to rendered video in MinIO
    thumbnail_url: str = ""  # URL to thumbnail in MinIO
    privacy_status: str = "private"  # private|unlisted|public
    category_id: str = "22"  # 22 = People & Blogs, 27 = Education, 26 = How-to


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


@app.post("/upload", response_model=ServiceResponse)
async def upload(req: DeliveryRequest):
    logger.info("delivery.uploading", content_id=req.content_id, title=req.title[:50])

    try:
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

        # Step 5: Log to DB
        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET youtube_video_id = $1, delivery_result = $2, "
                "status = 'delivered', updated_at = NOW() WHERE content_id = $3",
                youtube_video_id,
                __import__("json").dumps({
                    "youtube_video_id": youtube_video_id,
                    "privacy_status": req.privacy_status,
                    "url": f"https://youtu.be/{youtube_video_id}",
                }),
                req.content_id,
            )
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
