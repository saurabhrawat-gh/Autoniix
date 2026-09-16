from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StockRequest:
    query: str
    num_results: int = 10
    media_type: str = "video"  # "video" | "image"
    orientation: str | None = None  # "landscape" | "portrait" | "square"
    duration_min: int | None = None  # for video, in seconds
    duration_max: int | None = None  # for video, in seconds


@dataclass
class StockResult:
    results: list[dict] = field(default_factory=list)
    total_results: int = 0
    cost_usd: float = 0.0
    provider: str = ""
    cache_hit: bool = False


class StockProvider(ABC):
    """Abstract base for all stock footage/image providers."""

    @abstractmethod
    async def search(self, request: StockRequest) -> StockResult: ...

    @abstractmethod
    def estimate_cost(self, num_queries: int) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
