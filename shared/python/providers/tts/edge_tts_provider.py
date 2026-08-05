"""Edge TTS Provider — free Microsoft Edge text-to-speech for test mode.

Uses the `edge-tts` package which is completely free, no API key required.
Produces real MP3 audio at decent quality — good enough for pipeline testing.

Cost: $0.00
"""

from __future__ import annotations

import io
import struct
import tempfile
from pathlib import Path

import structlog

from providers.registry import ProviderRegistry
from providers.tts.base import TTSProvider, TTSRequest, TTSResult

logger = structlog.get_logger()

DEFAULT_VOICE = "en-US-AriaNeural"


class EdgeTTSProvider(TTSProvider):
    """Free TTS using Microsoft Edge voices via edge-tts package."""

    def __init__(self) -> None:
        self.voice: str = ""
        try:
            import edge_tts  # noqa: F401

            self._available = True
        except ImportError:
            logger.warning("edge_tts.not_installed", hint="pip install edge-tts")
            self._available = False

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        voice = request.voice_id or self.voice or DEFAULT_VOICE
        return await self.synthesize_with_params(
            text=request.text,
            voice_id=voice,
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
        if not self._available:
            return self._silence_fallback(text)

        import edge_tts

        voice = voice_id if voice_id and not voice_id.startswith("REPLACE_") else DEFAULT_VOICE

        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"

        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str)

        audio_bytes = b""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await communicate.save(tmp_path)
            audio_bytes = Path(tmp_path).read_bytes()
        except Exception as exc:
            logger.warning("edge_tts.synthesis_failed", error=str(exc))
            return self._silence_fallback(text)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        word_count = len(text.split())
        estimated_duration = (word_count / 150) * 60 / max(speed, 0.5)

        logger.info(
            "edge_tts.synthesized",
            chars=len(text),
            voice=voice,
            duration_s=round(estimated_duration, 2),
            bytes=len(audio_bytes),
        )

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=estimated_duration,
            word_count=word_count,
            bytes_charged=0,
            cost_usd=0.0,
            provider="edge_tts",
        )

    def _silence_fallback(self, text: str) -> TTSResult:
        """Return a minimal valid MP3-like silence if edge-tts is unavailable."""
        word_count = len(text.split())
        duration = (word_count / 150) * 60
        silence = self._generate_silence_wav(duration)

        logger.info("edge_tts.silence_fallback", words=word_count, duration_s=round(duration, 2))
        return TTSResult(
            audio_bytes=silence,
            duration_s=duration,
            word_count=word_count,
            bytes_charged=0,
            cost_usd=0.0,
            provider="edge_tts_silence",
        )

    @staticmethod
    def _generate_silence_wav(duration_s: float) -> bytes:
        """Generate a minimal WAV file of silence."""
        sample_rate = 22050
        num_samples = int(sample_rate * min(duration_s, 300))
        data_size = num_samples * 2

        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))
        buf.write(struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(b"\x00" * data_size)
        return buf.getvalue()

    async def get_word_timestamps(self, text: str, voice_id: str) -> dict:
        return {}

    def estimate_cost(self, text: str) -> float:
        return 0.0

    async def health_check(self) -> bool:
        return self._available

    def provider_name(self) -> str:
        return "edge_tts"


ProviderRegistry.register("tts", "edge_tts", EdgeTTSProvider)
