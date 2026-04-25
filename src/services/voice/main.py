from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.tts.fish_audio  # noqa: F401
import src.providers.storage.minio_provider  # noqa: F401
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


class VoiceRequest(BaseModel):
    content_id: str
    channel_id: str
    voice_id: str = ""
    segments: list[dict] = Field(default_factory=list)  # [{id, narration}]
    format: str = "mp3"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("voice.starting")
    yield
    await close_pool()
    logger.info("voice.stopped")


app = FastAPI(title="Voice Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="voice")


@app.post("/synthesize", response_model=ServiceResponse)
async def synthesize(req: VoiceRequest):
    logger.info("voice.synthesizing", content_id=req.content_id, segments=len(req.segments))

    tts = ProviderRegistry.get("tts")
    storage = ProviderRegistry.get("storage")

    from src.providers.tts.base import TTSRequest
    from src.providers.storage.base import StorageUpload

    full_text = " ".join(seg.get("narration", "") for seg in req.segments)
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="No narration text provided")

    total_cost = 0.0
    audio_segments = []

    try:
        # Synthesize full narration as one audio file
        tts_result = await tts.synthesize(TTSRequest(
            text=full_text,
            voice_id=req.voice_id or "default",
            format=req.format,
        ))
        total_cost += tts_result.cost_usd

        # Upload to MinIO
        audio_key = f"audio/{req.content_id}/narration.{req.format}"
        upload_result = await storage.upload(StorageUpload(
            key=audio_key,
            data=tts_result.audio_bytes,
            content_type=f"audio/{req.format}",
        ))

        audio_segments.append({
            "type": "full",
            "url": upload_result.url,
            "key": upload_result.key,
            "duration_s": tts_result.duration_s,
            "word_count": tts_result.word_count,
        })

        # Log usage
        try:
            pool = await get_pool()
            await pool.execute(
                "INSERT INTO api_usage (content_id, service, provider, model, cost_usd, latency_ms) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                req.content_id, "voice", tts_result.provider, "tts",
                float(total_cost), 0,
            )
        except Exception as e:
            logger.warning("voice.db_log_failed", error=str(e))

        logger.info("voice.synthesized", cost=total_cost, duration=tts_result.duration_s)

        return ServiceResponse(
            status="success",
            data={
                "audio_url": upload_result.url,
                "audio_key": upload_result.key,
                "duration_s": tts_result.duration_s,
                "word_count": tts_result.word_count,
                "segments": audio_segments,
            },
            cost={"cost_usd": total_cost, "provider": tts_result.provider},
        )

    except Exception as exc:
        logger.error("voice.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.voice.main:app", host="0.0.0.0", port=8003, log_level="info")
