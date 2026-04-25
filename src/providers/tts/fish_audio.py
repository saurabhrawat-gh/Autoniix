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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": request.text,
                    "reference_id": request.voice_id,
                    "format": request.format,
                    "bitrate": request.bitrate,
                },
            )
            response.raise_for_status()
            audio_bytes = response.content

        text_bytes = len(request.text.encode("utf-8"))
        cost = text_bytes * self.COST_PER_BYTE
        # Estimate duration from byte size (bitrate in kbps)
        duration_s = len(audio_bytes) / (request.bitrate * 1000 / 8)

        logger.info(
            "fish_audio.synthesized",
            chars=len(request.text),
            bytes_charged=text_bytes,
            cost_usd=round(cost, 6),
            duration_s=round(duration_s, 2),
        )

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=duration_s,
            word_count=len(request.text.split()),
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
