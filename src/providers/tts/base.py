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
    """Abstract base for all TTS providers."""

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult: ...

    @abstractmethod
    def estimate_cost(self, text: str) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
