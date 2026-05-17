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

import src.providers.boot  # noqa: F401

from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest
from src.providers.storage.base import StorageUpload

from src.services.voice.emotion_predictor import predict_emotions_for_sentences
from src.services.voice.audio_quality_scorer import analyze_audio_quality, score_emotion_variety
from src.services.voice.voice_style_learner import (
    extract_voice_features,
    predict_optimal_params,
    ingest_voice_feedback,
    train_voice_model,
)
from src.observability.metrics import instrument_app

logger = structlog.get_logger()


# Request Models

class VoiceRequest(BaseModel):
    channel_id: str
    content_id: str
    script_segments: list[dict] = Field(default_factory=list)
    voice_id: str = ""
    content_mode: str = "short"
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


# Helpers

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


# App

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("voice.starting")
    yield
    await close_pool()
    logger.info("voice.stopped")


from src.observability.sentry import init_sentry
init_sentry("voice")

app = FastAPI(title="Voice Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="voice")
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

        # Step 1: Split into sentences per segment
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
                    "prosody_hint": seg.get("prosody_hint", {}),
                })

        if not all_sentences:
            raise HTTPException(status_code=400, detail="No narration text in segments")

        # Step 2: Intelligence — Emotion Prediction
        # Check if we can use local prediction (saves LLM cost)
        use_prosody = await _load_config("voice_use_prosody_hints")
        has_prosody_hints = any(s.get("prosody_hint") for s in all_sentences)
        emotion_source = "local"

        if use_prosody != "false" and has_prosody_hints:
            # LOCAL PATH: Use emotion predictor (cost: $0.00)
            predicted_emotions = predict_emotions_for_sentences(all_sentences, channel)
            for i, sent in enumerate(all_sentences):
                em = predicted_emotions[i] if i < len(predicted_emotions) else {}
                sent["stability"] = em.get("stability", 0.50)
                sent["similarity_boost"] = em.get("similarity_boost", 0.75)
                sent["style"] = em.get("style", 0.40)
                sent["speed"] = em.get("speed", 1.0)
                sent["pause_after_ms"] = em.get("pause_after_ms", 300)
                sent["emotion"] = em.get("emotion", "neutral")
                sent["emphasis_words"] = em.get("emphasis_words", [])
                sent["volume_shift"] = em.get("volume_shift", "normal")
            logger.info("voice.emotion_predicted_locally", sentences=len(all_sentences))
        else:
            # LLM FALLBACK: Use GPT-4o-mini for emotion mapping
            emotion_source = "llm"
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

            try:
                emotion_data = _parse_json(em_result.content)
                emotion_sentences = emotion_data.get("sentences", [])
            except json.JSONDecodeError:
                emotion_sentences = []

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

        # Step 2B: Apply ML-learned optimal params (if model exists)
        niche = channel.get("niche", "general")
        optimal_params = await predict_optimal_params(req.channel_id, niche)
        if optimal_params:
            logger.info("voice.applying_ml_params", params=optimal_params)
            for sent in all_sentences:
                sent["stability"] = sent["stability"] * 0.7 + optimal_params.get("stability", sent["stability"]) * 0.3
                sent["similarity_boost"] = sent["similarity_boost"] * 0.7 + optimal_params.get("similarity_boost", sent["similarity_boost"]) * 0.3

        # Step 3: Per-Sentence TTS
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

        # Step 4: Concatenate audio + upload
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

        # Step 5: Validation
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

        # Step 5B: Intelligence — Audio Quality Analysis
        audio_analysis = await analyze_audio_quality(
            combined_audio, expected_duration_s=total_duration)
        emotion_variety = score_emotion_variety(
            [{"emotion": s.get("emotion", "neutral")} for s in all_sentences])

        # Step 6: Quality score (enhanced with intelligence)
        quality_score = 10.0

        # WPM check
        if not validation["wpm_ok"]:
            quality_score -= 1.5
            validation["wpm_issue"] = f"WPM {wpm:.0f} outside 130-170 range"

        # Duration check
        if total_duration < 10:
            quality_score -= 0.5

        # Audio quality from librosa analysis
        audio_score = audio_analysis.get("quality_score", 7.0)
        if audio_score < 5.0:
            quality_score -= 2.0
            validation["audio_quality"] = f"Poor audio quality: {audio_score}"
        elif audio_score < 7.0:
            quality_score -= 1.0
            validation["audio_quality"] = f"Fair audio quality: {audio_score}"
        else:
            validation["audio_quality"] = f"Good audio quality: {audio_score}"

        # Naturalness score
        naturalness = audio_analysis.get("naturalness_score", 7.0)
        validation["naturalness_score"] = naturalness

        # Emotion variety check (using intelligence scorer)
        variety_score = emotion_variety.get("variety_score", 5.0)
        unique_emotions = set(s.get("emotion", "neutral") for s in all_sentences)
        if len(unique_emotions) <= 1:
            quality_score -= 1.0
            validation["emotion_variety"] = "low — only one emotion detected"
        elif len(unique_emotions) <= 2:
            quality_score -= 0.5
            validation["emotion_variety"] = "moderate — only 2 emotions"
        else:
            validation["emotion_variety"] = f"good — {len(unique_emotions)} distinct emotions"
        validation["emotion_variety_score"] = variety_score

        # Segment coverage check
        covered_segments = set(s["segment_id"] for s in all_sentences)
        total_segments = set(seg.get("id", "") for seg in req.script_segments if seg.get("narration"))
        missing_segs = total_segments - covered_segments
        if missing_segs:
            quality_score -= len(missing_segs) * 0.5
            validation["missing_segments"] = list(missing_segs)

        quality_score = max(1.0, round(quality_score, 1))

        # Step 6B: Intelligence — Store features for ML
        await extract_voice_features(
            req.content_id, req.channel_id,
            audio_analysis.get("metrics", {}),
            [{"emotion": s.get("emotion"), "stability": s.get("stability"),
              "similarity_boost": s.get("similarity_boost"), "style": s.get("style"),
              "speed": s.get("speed"), "pause_after_ms": s.get("pause_after_ms"),
              "emphasis_words": s.get("emphasis_words", [])}
             for s in all_sentences],
            validation)

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
            "intelligence": {
                "emotion_source": emotion_source,
                "audio_analysis": {
                    "quality_score": audio_analysis.get("quality_score"),
                    "naturalness_score": audio_analysis.get("naturalness_score"),
                    "snr_db": audio_analysis.get("metrics", {}).get("snr_db"),
                },
                "emotion_variety": emotion_variety,
                "ml_params_applied": optimal_params is not None,
                "llm_cost_saved": emotion_source == "local",
            },
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


# Intelligence Endpoints

class VoiceFeedbackRequest(BaseModel):
    content_id: str
    channel_id: str
    retention_data: dict = Field(default_factory=dict)


class VoiceTrainRequest(BaseModel):
    niche: str


@app.post("/voice-feedback", response_model=ServiceResponse)
async def voice_feedback(req: VoiceFeedbackRequest):
    """Ingest retention data for voice ML learning."""
    ok = await ingest_voice_feedback(req.content_id, req.channel_id, req.retention_data)
    return ServiceResponse(status="success" if ok else "failed", data={"ingested": ok})


@app.post("/voice-train", response_model=ServiceResponse)
async def voice_train(req: VoiceTrainRequest):
    """Train/retrain voice parameter optimization model."""
    result = await train_voice_model(req.niche)
    return ServiceResponse(status="success", data=result)


async def _load_config(key: str) -> str:
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = $1", key)
        return row["config_value"] if row else ""
    except Exception:
        return ""


if __name__ == "__main__":
    uvicorn.run("src.services.voice.main:app", host="0.0.0.0", port=8003, log_level="info")
