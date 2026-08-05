from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    messages: list[dict] = field(default_factory=list)
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4000
    response_format: str = "text"  # "text" | "json"


@dataclass
class LLMResult:
    content: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    provider: str = ""
    latency_ms: int = 0
    finish_reason: str = "stop"
    compression: Any | None = None  # CompressionStats from llm.compressor


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResult: ...

    @abstractmethod
    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    def supported_models(self) -> list[str]: ...
