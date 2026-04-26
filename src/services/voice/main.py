from __future__ import annotations

import io
import json
import re
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.tts.fish_audio  # noqa: F401
import src.providers.tts.elevenlabs_provider  # noqa: F401
import src.providers.storage.minio_provider  # noqa: F401
import src.providers.llm.openai_provider  # noqa: F401

from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest
from src.providers.storage.base import StorageUpload

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class VoiceRequest(BaseModel):
    channel_id: str
    content_id: str
    script_segments: list[dict] = Field(default_factory=list)
    voice_id: str = ""
    content_mode: str = "short"
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


# ── Helpers ──────────────────────────────────────────────────

def _safe_format(template: str, **kwargs) -> str:
    """Replace {key} placeholders without failing on unknown/literal braces."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


async def _load_prompt(prompt_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT system_prompt, user_prompt_template FROM prompt_registry "
        "WHERE prompt_id = $1 AND is_active = true", prompt_id)
    return dict(row) if row else {}


async def _log_usage(content_id: str, service: str, provider: str, model: str,
                     tokens_in: int, tokens_out: int, cost: float, latency: int = 0):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            content_id, service, provider, model, tokens_in, tokens_out, float(cost), latency)
    except Exception as e:
        logger.warning("voice.db_log_failed", error=str(e))


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for per-sentence TTS."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


# ── App ──────────────────────────────────────────────────────

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
    """Full voice pipeline: split → emotion map → per-sentence TTS → validate → quality gate."""
    logger.info("voice.synthesizing", channel_id=req.channel_id, segments=len(req.script_segments))
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        voice_id = req.voice_id or channel.get("voice_id", "")
        if not voice_id or voice_id.startswith("REPLACE_"):
            voice_id = ""  # provider will use its own default

        tts = ProviderRegistry.get("tts")
        storage = ProviderRegistry.get("storage")

        # ── Step 1: Split into sentences per segment ─────
        all_sentences = []
        for seg in req.script_segments:
            narration = seg.get("narration", "")
            if not narration:
                continue
            sentences = _split_sentences(narration)
            for sent in sentences:
                all_sentences.append({
                    "segment_id": seg.get("id", ""),
                    "section": seg.get("section", "body"),
                    "text": sent,
                })

        if not all_sentences:
            raise HTTPException(status_code=400, detail="No narration text in segments")

        # ── Step 2: Emotion Mapping (GPT-4o-mini) ────────
        emotion_prompt = await _load_prompt("PRM_B2_EMOTION_MAP")
        emotion_llm = ProviderRegistry.get("llm.emotion")

        full_narration = " ".join(s["text"] for s in all_sentences)

        em_system = emotion_prompt.get("system_prompt",
            "Map emotions to voice parameters per sentence. Respond in JSON.")
        em_user = _safe_format(emotion_prompt.get("user_prompt_template",
            "Narration: {narration}\nVoice style: {brand_voice}"),
            narration=full_narration[:3000],
            brand_voice=channel.get("brand_voice", ""),
            pacing_style=channel.get("pacing_style", ""),
        )

        em_result = await emotion_llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": em_system},
                {"role": "user", "content": em_user},
            ],
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2000,
            response_format="json",
        ))
        total_cost += em_result.cost_usd
        await _log_usage(req.content_id, "voice_emotion", em_result.provider,
                         em_result.model, em_result.tokens_in, em_result.tokens_out,
                         em_result.cost_usd, em_result.latency_ms)

        # Parse emotion map
        try:
            emotion_data = _parse_json(em_result.content)
            emotion_sentences = emotion_data.get("sentences", [])
        except json.JSONDecodeError:
            emotion_sentences = []

        # Merge emotion params into sentences
        default_stability = float(channel.get("voice_stability", 0.50))
        default_similarity = float(channel.get("voice_similarity", 0.75))
        default_style = float(channel.get("voice_style", 0.40))

        for i, sent in enumerate(all_sentences):
            if i < len(emotion_sentences):
                em = emotion_sentences[i]
                sent["stability"] = float(em.get("stability", default_stability))
                sent["similarity_boost"] = float(em.get("similarity_boost", default_similarity))
                sent["style"] = float(em.get("style", default_style))
                sent["speed"] = float(em.get("speed", 1.0))
                sent["pause_after_ms"] = int(em.get("pause_after_ms", 300))
                sent["emotion"] = em.get("emotion", "neutral")
                sent["emphasis_words"] = em.get("emphasis_words", [])
                sent["volume_shift"] = em.get("volume_shift", "normal")
            else:
                sent["stability"] = default_stability
                sent["similarity_boost"] = default_similarity
                sent["style"] = default_style
                sent["speed"] = 1.0
                sent["pause_after_ms"] = 300
                sent["emotion"] = "neutral"
                sent["emphasis_words"] = []
                sent["volume_shift"] = "normal"

        # ── Step 3: Per-Sentence TTS ─────────────────────
        audio_chunks = []
        total_duration = 0.0
        total_chars = 0
        tts_provider_name = tts.provider_name()

        for sent in all_sentences:
            tts_result = await tts.synthesize_with_params(
                text=sent["text"],
                voice_id=voice_id,
                stability=sent["stability"],
                similarity_boost=sent["similarity_boost"],
                style=sent["style"],
                speed=sent.get("speed", 1.0),
            )

            audio_chunks.append({
                "segment_id": sent["segment_id"],
                "text": sent["text"],
                "emotion": sent.get("emotion", "neutral"),
                "audio_bytes": tts_result.audio_bytes,
                "duration_s": tts_result.duration_s,
                "pause_after_ms": sent.get("pause_after_ms", 300),
            })
            total_duration += tts_result.duration_s
            total_chars += len(sent["text"])
            total_cost += tts_result.cost_usd

        # ── Step 4: Concatenate audio + upload ───────────
        # Simple concatenation (in production, use pydub/ffmpeg for proper concat with pauses)
        combined_audio = b"".join(chunk["audio_bytes"] for chunk in audio_chunks)

        key = f"voice/{req.content_id}/narration.mp3"
        sr = await storage.upload(StorageUpload(key=key, data=combined_audio, content_type="audio/mpeg"))
        url = sr.url

        # Also upload per-segment audio
        segment_urls = {}
        current_seg = None
        seg_audio = b""
        for chunk in audio_chunks:
            if chunk["segment_id"] != current_seg:
                if current_seg and seg_audio:
                    seg_key = f"voice/{req.content_id}/{current_seg}.mp3"
                    seg_sr = await storage.upload(StorageUpload(key=seg_key, data=seg_audio, content_type="audio/mpeg"))
                    segment_urls[current_seg] = seg_sr.url
                current_seg = chunk["segment_id"]
                seg_audio = b""
            seg_audio += chunk["audio_bytes"]
        if current_seg and seg_audio:
            seg_key = f"voice/{req.content_id}/{current_seg}.mp3"
            seg_sr = await storage.upload(StorageUpload(key=seg_key, data=seg_audio, content_type="audio/mpeg"))
            segment_urls[current_seg] = seg_sr.url

        # ── Step 5: Validation ───────────────────────────
        word_count = sum(len(s["text"].split()) for s in all_sentences)
        wpm = (word_count / total_duration * 60) if total_duration > 0 else 0

        validation = {
            "total_duration_s": round(total_duration, 2),
            "word_count": word_count,
            "wpm": round(wpm, 1),
            "wpm_ok": 130 <= wpm <= 170,
            "sentence_count": len(all_sentences),
            "total_chars": total_chars,
        }

        # ── Step 6: Quality score (enhanced) ──────────
        quality_score = 10.0

        # WPM check
        if not validation["wpm_ok"]:
            quality_score -= 1.5
            validation["wpm_issue"] = f"WPM {wpm:.0f} outside 130-170 range"

        # Duration check
        if total_duration < 10:
            quality_score -= 0.5

        # Emotion variety check
        unique_emotions = set(s.get("emotion", "neutral") for s in all_sentences)
        if len(unique_emotions) <= 1:
            quality_score -= 1.0
            validation["emotion_variety"] = "low — only one emotion detected"
        elif len(unique_emotions) <= 2:
            quality_score -= 0.5
            validation["emotion_variety"] = "moderate — only 2 emotions"
        else:
            validation["emotion_variety"] = f"good — {len(unique_emotions)} distinct emotions"

        # Segment coverage check
        covered_segments = set(s["segment_id"] for s in all_sentences)
        total_segments = set(seg.get("id", "") for seg in req.script_segments if seg.get("narration"))
        missing_segs = total_segments - covered_segments
        if missing_segs:
            quality_score -= len(missing_segs) * 0.5
            validation["missing_segments"] = list(missing_segs)

        quality_score = max(1.0, round(quality_score, 1))

        # Log usage
        await _log_usage(req.content_id, "voice", tts_provider_name, "tts",
                         total_chars, 0, total_cost, 0)

        # Build audio manifest
        manifest = {
            "audio_url": url,
            "segment_urls": segment_urls,
            "duration_s": round(total_duration, 2),
            "word_count": word_count,
            "sentence_count": len(all_sentences),
            "emotion_map": [
                {
                    "segment_id": s["segment_id"],
                    "text": s["text"][:80],
                    "emotion": s.get("emotion", "neutral"),
                    "emphasis_words": s.get("emphasis_words", []),
                    "volume_shift": s.get("volume_shift", "normal"),
                    "speed": s.get("speed", 1.0),
                    "pause_after_ms": s.get("pause_after_ms", 300),
                }
                for s in all_sentences
            ],
            "validation": validation,
            "voice_quality_score": round(quality_score, 1),
        }

        logger.info("voice.completed",
                     duration=round(total_duration, 1),
                     sentences=len(all_sentences),
                     quality=quality_score,
                     cost=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data=manifest,
            cost={"cost_usd": round(total_cost, 6), "provider": tts_provider_name},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("voice.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.voice.main:app", host="0.0.0.0", port=8003, log_level="info")
