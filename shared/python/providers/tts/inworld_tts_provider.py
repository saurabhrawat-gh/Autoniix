from __future__ import annotations

import base64
import re
import time

import httpx
import structlog

from core.config import settings
from providers.registry import ProviderRegistry
from providers.tts.base import TTSProvider, TTSRequest, TTSResult

logger = structlog.get_logger()

PRICING: dict[str, float] = {
    "inworld-tts-2": 25.0 / 1_000_000,
    "inworld-tts-1-max": 25.0 / 1_000_000,
    "inworld-tts-1": 15.0 / 1_000_000,
}

_EMOTION_INSTRUCTIONS: dict[str, str] = {
    "happy": "[speak warmly and enthusiastically] ",
    "excited": "[speak with high energy and excitement] ",
    "calm": "[speak calmly and steadily] ",
    "serious": "[speak seriously and authoritatively] ",
    "sad": "[speak with a somber, reflective tone] ",
    "curious": "[speak with curiosity and wonder] ",
    "friendly": "[speak conversationally and in a friendly tone] ",
    "dramatic": "[speak dramatically with strong emphasis] ",
    "neutral": "[speak naturally and clearly] ",
}
_DEFAULT_INSTRUCTION = "[speak naturally and engagingly] "

_MAX_CHARS = 2000


def _delivery_mode(stability: float, style: float) -> str:
    """Map abstract stability/style knobs → Inworld deliveryMode.
    High style or low stability → CREATIVE (more expressive).
    Low style and high stability → STABLE (consistent).
    Middle ground → BALANCED.
    """
    expressiveness = (style + (1.0 - stability)) / 2.0
    if expressiveness >= 0.65:
        return "CREATIVE"
    if expressiveness <= 0.30:
        return "STABLE"
    return "BALANCED"


def _chunk_text(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """Split text into ≤max_chars chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip() if current else sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_chars:
                words = sentence.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= max_chars:
                        current = (current + " " + word).strip() if current else word
                    else:
                        if current:
                            chunks.append(current)
                        current = word
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


class InworldTTSProvider(TTSProvider):
    BASE_URL = "https://api.inworld.ai/tts/v1/voice"

    def __init__(self) -> None:
        self.api_key = settings.inworld_api_key
        self.model = settings.inworld_tts_model
        self.default_voice = settings.inworld_voice_id
        if not self.api_key:
            logger.warning("inworld_tts.no_api_key")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        instruction = (
            _EMOTION_INSTRUCTIONS.get(request.emotion or "", _DEFAULT_INSTRUCTION)
            if self.model == "inworld-tts-2"
            else ""
        )
        return await self._synthesize_full(
            text=request.text,
            voice_id=request.voice_id or self.default_voice,
            instruction_prefix=instruction,
            delivery_mode="BALANCED",
            speed=1.0,
        )

    async def synthesize_with_params(
        self,
        text: str,
        voice_id: str,
        stability: float = 0.50,
        similarity_boost: float = 0.75,
        style: float = 0.40,
        speed: float = 1.0,
    ) -> TTSResult:
        """Map abstract emotion knobs → Inworld API params.

        stability     → deliveryMode (high stability = STABLE)
        style         → deliveryMode (high style = CREATIVE)
        similarity_boost → temperature proxy (non-TTS-2 models only)
        speed         → talkingSpeed (0.5–1.5 on Inworld)
        """
        delivery = _delivery_mode(stability, style) if self.model == "inworld-tts-2" else "BALANCED"
        temperature = round(max(0.1, min(2.0, 2.0 - similarity_boost)), 2)
        clamped_speed = round(max(0.5, min(1.5, speed)), 2)

        return await self._synthesize_full(
            text=text,
            voice_id=voice_id or self.default_voice,
            instruction_prefix="",
            delivery_mode=delivery,
            temperature=temperature,
            speed=clamped_speed,
        )

    async def _synthesize_full(
        self,
        text: str,
        voice_id: str,
        instruction_prefix: str = "",
        delivery_mode: str = "BALANCED",
        temperature: float = 1.0,
        speed: float = 1.0,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError(
                "inworld_tts provider has no api_key configured. "
                "Set INWORLD_API_KEY or switch TTS_PROVIDER back to 'fishaudio'."
            )

        full_text = (instruction_prefix + text) if instruction_prefix else text
        chunks = _chunk_text(full_text)
        all_audio = bytearray()
        total_chars = 0
        start = time.monotonic()

        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for chunk in chunks:
                body: dict = {
                    "text": chunk,
                    "voiceId": voice_id,
                    "modelId": self.model,
                    "audioConfig": {
                        "audioEncoding": "MP3",
                        "sampleRateHertz": 24000,
                    },
                    "applyTextNormalization": "ON",
                }
                if self.model == "inworld-tts-2":
                    body["deliveryMode"] = delivery_mode
                else:
                    body["temperature"] = temperature
                if speed != 1.0:
                    body["talkingSpeed"] = speed

                response = await client.post(self.BASE_URL, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()

                audio_b64 = data.get("audioContent", "")
                if audio_b64:
                    all_audio.extend(base64.b64decode(audio_b64))
                total_chars += data.get("usage", {}).get("processedCharactersCount", len(chunk))

        audio_bytes = bytes(all_audio)
        cost = total_chars * PRICING.get(self.model, PRICING["inworld-tts-2"])
        word_count = len(text.split())
        estimated_duration = (word_count / 150) * 60 / max(speed, 0.5)
        latency_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "inworld_tts.synthesized",
            model=self.model,
            voice_id=voice_id,
            chars=total_chars,
            chunks=len(chunks),
            cost_usd=round(cost, 6),
            duration_s=round(estimated_duration, 2),
            latency_ms=latency_ms,
        )

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=estimated_duration,
            word_count=word_count,
            bytes_charged=total_chars,
            cost_usd=cost,
            provider="inworld",
        )

    async def get_word_timestamps(self, text: str, voice_id: str) -> dict:
        """Inworld supports word-level alignment — useful for captions/lip-sync."""
        if not self.api_key:
            return {}
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "text": text[:_MAX_CHARS],
            "voiceId": voice_id or self.default_voice,
            "modelId": self.model,
            "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000},
            "timestampType": "WORD",
            "applyTextNormalization": "ON",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.BASE_URL, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
            return data.get("timestampInfo", {})
        except Exception:
            return {}

    def estimate_cost(self, text: str) -> float:
        return len(text) * PRICING.get(self.model, PRICING["inworld-tts-2"])

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.inworld.ai/tts/v1/voices",
                    headers={"Authorization": f"Basic {self.api_key}"},
                )
                return resp.status_code < 500
        except Exception:
            return False

    def provider_name(self) -> str:
        return "inworld"


ProviderRegistry.register("tts", "inworld", InworldTTSProvider)
ProviderRegistry.register("tts", "inworldai", InworldTTSProvider)
ProviderRegistry.register("tts", "inworldtts", InworldTTSProvider)
