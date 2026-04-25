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


class AssetsRequest(BaseModel):
    content_id: str
    channel_id: str
    segments: list[dict] = Field(default_factory=list)  # [{id, scene_direction, asset_suggestions, b_roll_keywords}]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("assets.starting")
    yield
    await close_pool()
    logger.info("assets.stopped")


app = FastAPI(title="Assets Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="assets")


@app.post("/generate-assets", response_model=ServiceResponse)
async def generate_assets(req: AssetsRequest):
    logger.info("assets.generating", content_id=req.content_id, segments=len(req.segments))

    image_provider = ProviderRegistry.get("image")
    storage = ProviderRegistry.get("storage")

    from src.providers.image.base import ImageRequest
    from src.providers.storage.base import StorageUpload

    total_cost = 0.0
    manifest = []

    for seg in req.segments:
        seg_id = seg.get("id", "unknown")
        direction = seg.get("scene_direction", "")
        suggestions = seg.get("asset_suggestions", [])

        if not direction and not suggestions:
            manifest.append({"segment_id": seg_id, "type": "none", "assets": []})
            continue

        try:
            # Generate image via DALL-E
            prompt = f"YouTube video scene: {direction}. {', '.join(suggestions[:3])}"
            prompt = prompt[:900]  # DALL-E prompt limit

            img_result = await image_provider.generate(ImageRequest(
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                style="vivid",
                n=1,
            ))
            total_cost += img_result.cost_usd

            # Download and upload to MinIO
            assets = []
            for i, img in enumerate(img_result.images):
                img_url = img.get("url", "")
                if not img_url:
                    continue

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(img_url)
                    resp.raise_for_status()
                    img_bytes = resp.content

                key = f"assets/{req.content_id}/{seg_id}_{i}.png"
                upload = await storage.upload(StorageUpload(
                    key=key,
                    data=img_bytes,
                    content_type="image/png",
                ))

                assets.append({
                    "url": upload.url,
                    "key": upload.key,
                    "type": "generated",
                    "prompt": prompt[:200],
                })

            manifest.append({
                "segment_id": seg_id,
                "type": "generated",
                "assets": assets,
            })

        except Exception as exc:
            logger.warning("assets.segment_failed", segment_id=seg_id, error=str(exc))
            manifest.append({"segment_id": seg_id, "type": "failed", "error": str(exc), "assets": []})

    # Log usage
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, cost_usd) VALUES ($1, $2, $3, $4)",
            req.content_id, "assets", "dalle", float(total_cost),
        )
    except Exception as e:
        logger.warning("assets.db_log_failed", error=str(e))

    logger.info("assets.generated", total_assets=sum(len(m.get("assets", [])) for m in manifest), cost=total_cost)

    return ServiceResponse(
        status="success",
        data={"manifest": manifest, "total_assets": sum(len(m.get("assets", [])) for m in manifest)},
        cost={"cost_usd": total_cost, "provider": "dalle"},
    )


if __name__ == "__main__":
    uvicorn.run("src.services.assets.main:app", host="0.0.0.0", port=8004, log_level="info")
