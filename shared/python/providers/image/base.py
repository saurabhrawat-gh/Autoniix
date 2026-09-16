from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ImageRequest:
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"  # "standard" | "hd"
    style: str = "vivid"  # "vivid" | "natural"
    n: int = 1


@dataclass
class ImageResult:
    images: list[dict] = field(default_factory=list)  # [{url, revised_prompt}]
    cost_usd: float = 0.0
    provider: str = ""


class ImageProvider(ABC):
    """Abstract base for all image generation providers."""

    @abstractmethod
    async def generate(self, request: ImageRequest) -> ImageResult: ...

    @abstractmethod
    def estimate_cost(self, n: int, quality: str, size: str) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
