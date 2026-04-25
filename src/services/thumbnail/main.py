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

import src.providers.image.dalle_provider  # noqa: F401
import src.providers.storage.minio_provider  # noqa: F401
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


class ThumbnailRequest(BaseModel):
    content_id: str
    channel_id: str
    title: str
    niche: str = ""
    style_hints: dict = Field(default_factory=dict)  # {primary_color, accent_color, ...}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("thumbnail.starting")
    yield
    await close_pool()
    logger.info("thumbnail.stopped")


app = FastAPI(title="Thumbnail Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="thumbnail")


THUMBNAIL_PROMPT_TEMPLATE = (
    "Create a highly click-worthy YouTube thumbnail for the video titled: \"{title}\". "
    "Style: Bold, vibrant, cinematic. Use dramatic lighting and strong contrast. "
    "Include large, readable text overlay area on the left side. "
    "The image should be eye-catching and professional. "
    "Niche: {niche}. Do NOT include any text in the image itself. "
    "Aspect ratio: 16:9, resolution optimized for 1280x720."
)


@app.post("/generate-thumbnail", response_model=ServiceResponse)
async def generate_thumbnail(req: ThumbnailRequest):
    logger.info("thumbnail.generating", content_id=req.content_id, title=req.title[:50])

    image_provider = ProviderRegistry.get("image")
    storage = ProviderRegistry.get("storage")

    from src.providers.image.base import ImageRequest
    from src.providers.storage.base import StorageUpload

    try:
        prompt = THUMBNAIL_PROMPT_TEMPLATE.format(
            title=req.title[:200],
            niche=req.niche or "general",
        )

        img_result = await image_provider.generate(ImageRequest(
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            style="vivid",
            n=1,
        ))

        # Download and store in MinIO
        img_url = img_result.images[0]["url"] if img_result.images else ""
        if not img_url:
            raise HTTPException(status_code=500, detail="No image generated")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(img_url)
            resp.raise_for_status()
            img_bytes = resp.content

        key = f"thumbnails/{req.content_id}/thumbnail.png"
        upload = await storage.upload(StorageUpload(
            key=key,
            data=img_bytes,
            content_type="image/png",
        ))

        # Log usage
        try:
            pool = await get_pool()
            await pool.execute(
                "INSERT INTO api_usage (content_id, service, provider, cost_usd) VALUES ($1, $2, $3, $4)",
                req.content_id, "thumbnail", "dalle", float(img_result.cost_usd),
            )
        except Exception as e:
            logger.warning("thumbnail.db_log_failed", error=str(e))

        logger.info("thumbnail.generated", cost=img_result.cost_usd)

        return ServiceResponse(
            status="success",
            data={
                "thumbnail_url": upload.url,
                "thumbnail_key": upload.key,
                "revised_prompt": img_result.images[0].get("revised_prompt", ""),
            },
            cost={"cost_usd": img_result.cost_usd, "provider": "dalle"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("thumbnail.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.thumbnail.main:app", host="0.0.0.0", port=8005, log_level="info")
