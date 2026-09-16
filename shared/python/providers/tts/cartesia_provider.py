from __future__ import annotations

import httpx
import structlog

from core.config import settings
from providers.registry import ProviderRegistry
from providers.tts.base import TTSProvider, TTSRequest, TTSResult

logger = structlog.get_logger()

COST_PER_1K_CHARS = 0.25


class CartesiaTTS(TTSProvider):
    BASE_URL = "https://api.cartesia.ai"

    def __init__(self) -> None:
        self.api_key = settings.cartesia_api_key
        if not self.api_key:
            logger.warning("cartesia.no_api_key")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        word_count = len(request.text.split())

        body = {
            "model_id": "sonic-english",
            "text": request.text,
            "voice": {
                "mode": "id",
                "id": request.voice_id or "79a125e8-cd45-4c13-8a67-188112f4dd22",
            },
            "output_format": {
                "container": "mp3",
                "sample_rate": 44100,
                "bit_rate": 128000,
            },
        }

        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/tts/websockets",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            audio_bytes = response.content

        chars = len(request.text)
        cost = (chars / 1000) * COST_PER_1K_CHARS
        estimated_duration = (word_count / 150) * 60

        logger.info(
            "cartesia.synthesized",
            voice_id=request.voice_id,
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
            provider="cartesia",
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

        body = {
            "model_id": "sonic-english",
            "text": text,
            "voice": {
                "mode": "id",
                "id": voice_id or "79a125e8-cd45-4c13-8a67-188112f4dd22",
            },
            "output_format": {
                "container": "mp3",
                "sample_rate": 44100,
                "bit_rate": 128000,
            },
            "speed": speed,
        }

        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/tts/websockets",
                headers=headers,
                json=body,
            )
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
            provider="cartesia",
        )

    def estimate_cost(self, text: str) -> float:
        return (len(text) / 1000) * COST_PER_1K_CHARS

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/voices",
                    headers={"X-API-Key": self.api_key},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "cartesia"


ProviderRegistry.register("tts", "cartesia", CartesiaTTS)
