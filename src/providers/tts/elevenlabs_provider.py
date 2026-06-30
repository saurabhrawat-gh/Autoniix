from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.tts.base import TTSProvider, TTSRequest, TTSResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

COST_PER_1K_CHARS = 0.30


class ElevenLabsTTS(TTSProvider):
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self) -> None:
        self.api_key = settings.elevenlabs_api_key
        self.model_id = settings.elevenlabs_model_id
        if not self.api_key:
            logger.warning("elevenlabs.no_api_key")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        voice_id = request.voice_id or "21m00Tcm4TlvDq8ikWAM"
        word_count = len(request.text.split())

        voice_settings = {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.40,
            "use_speaker_boost": True,
        }

        body = {
            "text": request.text,
            "model_id": self.model_id,
            "voice_settings": voice_settings,
            "output_format": "mp3_44100_128",
        }

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            audio_bytes = response.content

        chars = len(request.text)
        cost = (chars / 1000) * COST_PER_1K_CHARS
        estimated_duration = (word_count / 150) * 60

        logger.info(
            "elevenlabs.synthesized",
            voice_id=voice_id,
            chars=chars,
            words=word_count,
            cost_usd=round(cost, 4),
            bytes=len(audio_bytes),
        )

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=estimated_duration,
            word_count=word_count,
            bytes_charged=chars,
            cost_usd=cost,
            provider="elevenlabs",
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
        """Synthesize with per-sentence emotion parameters."""
        word_count = len(text.split())

        voice_settings = {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        }

        body = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": voice_settings,
            "output_format": "mp3_44100_128",
        }

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            audio_bytes = response.content

        chars = len(text)
        cost = (chars / 1000) * COST_PER_1K_CHARS
        estimated_duration = (word_count / 150) * 60

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=estimated_duration,
            word_count=word_count,
            bytes_charged=chars,
            cost_usd=cost,
            provider="elevenlabs",
        )

    async def get_word_timestamps(self, text: str, voice_id: str) -> dict:
        """Use ElevenLabs streaming with timestamps for word-level sync."""
        body = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.75,
                "style": 0.40,
            },
            "output_format": "mp3_44100_128",
        }

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/with-timestamps"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    def estimate_cost(self, text: str) -> float:
        return (len(text) / 1000) * COST_PER_1K_CHARS

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/user/subscription",
                    headers={"xi-api-key": self.api_key},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "elevenlabs"


ProviderRegistry.register("tts", "elevenlabs", ElevenLabsTTS)
