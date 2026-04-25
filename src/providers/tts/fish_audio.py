from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.registry import ProviderRegistry
from src.providers.tts.base import TTSProvider, TTSRequest, TTSResult

logger = structlog.get_logger()


class FishAudioTTS(TTSProvider):
    BASE_URL = "https://api.fish.audio/v1/tts"
    COST_PER_BYTE = 15.0 / 1_000_000  # $15 per 1M UTF-8 bytes

    def __init__(self) -> None:
        self.api_key = settings.fish_audio_api_key
        if not self.api_key:
            logger.warning("fish_audio.no_api_key")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        return await self._do_synthesize(
            text=request.text,
            voice_id=request.voice_id,
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
        """Fish Audio emotion mapping:
        - stability → top_p (high stability = low randomness)
        - similarity_boost → not directly supported, ignored
        - style → temperature (high style = high expressiveness)
        - speed → speed multiplier
        """
        return await self._do_synthesize(
            text=text,
            voice_id=voice_id,
            speed=speed,
            temperature=max(0.1, min(1.0, style)),
            top_p=max(0.1, min(1.0, stability)),
        )

    async def _do_synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        temperature: float = 0.7,
        top_p: float = 0.8,
    ) -> TTSResult:
        """Core synthesis call to Fish Audio API."""
        body = {
            "text": text,
            "reference_id": voice_id,
            "format": "mp3",
            "bitrate": 128,
        }
        # Fish Audio supports prosody control via these params
        if speed != 1.0:
            body["speed"] = speed
        if temperature != 0.7:
            body["temperature"] = temperature
        if top_p != 0.8:
            body["top_p"] = top_p

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
            audio_bytes = response.content

        text_bytes = len(text.encode("utf-8"))
        cost = text_bytes * self.COST_PER_BYTE
        word_count = len(text.split())
        # Estimate duration: ~150 WPM adjusted by speed
        estimated_duration = (word_count / 150) * 60 / max(speed, 0.5)

        logger.info(
            "fish_audio.synthesized",
            chars=len(text),
            bytes_charged=text_bytes,
            cost_usd=round(cost, 6),
            duration_s=round(estimated_duration, 2),
            speed=speed,
        )

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=estimated_duration,
            word_count=word_count,
            bytes_charged=text_bytes,
            cost_usd=cost,
            provider="fish_audio",
        )

    def estimate_cost(self, text: str) -> float:
        return len(text.encode("utf-8")) * self.COST_PER_BYTE

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.fish.audio/",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code < 500
        except Exception:
            return False

    def provider_name(self) -> str:
        return "fish_audio"


ProviderRegistry.register("tts", "fish_audio", FishAudioTTS)
ProviderRegistry.register("tts", "fishaudio", FishAudioTTS)
