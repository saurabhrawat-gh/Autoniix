from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TTSRequest:
    text: str
    voice_id: str
    emotion: str | None = None
    emphasis_words: list[str] = field(default_factory=list)
    target_wpm: int = 150
    format: str = "mp3"
    bitrate: int = 128


@dataclass
class TTSResult:
    audio_bytes: bytes
    duration_s: float
    word_count: int
    bytes_charged: int
    cost_usd: float
    provider: str
    cache_hit: bool = False


class TTSProvider(ABC):
    """Abstract base for all TTS providers.

    Every TTS provider MUST implement:
      - synthesize(request)             → basic synthesis
      - synthesize_with_params(...)     → emotion-mapped per-sentence synthesis
      - estimate_cost(text)
      - health_check()
      - provider_name()

    Optionally:
      - get_word_timestamps(text, voice_id) → word-level sync data
    """

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult: ...

    @abstractmethod
    async def synthesize_with_params(
        self,
        text: str,
        voice_id: str,
        stability: float = 0.50,
        similarity_boost: float = 0.75,
        style: float = 0.40,
        speed: float = 1.0,
    ) -> TTSResult:
        """Synthesize with per-sentence emotion parameters.

        All TTS providers must map these abstract knobs to their native API:
          - stability:        voice consistency (0=varied, 1=stable)
          - similarity_boost: how close to reference voice (0=loose, 1=exact)
          - style:            expressiveness / emotion intensity (0=flat, 1=dramatic)
          - speed:            playback speed multiplier (0.5=half, 2.0=double)
        """
        ...

    async def get_word_timestamps(self, text: str, voice_id: str) -> dict:
        """Optional: return word-level timestamps for lip-sync / captions.
        Default returns empty — providers override if supported.
        """
        return {}

    @abstractmethod
    def estimate_cost(self, text: str) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
