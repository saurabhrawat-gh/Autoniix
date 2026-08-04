from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchRequest:
    query: str
    num_results: int = 10
    search_type: str = "web"  # "web" | "video" | "news"
    domain_filter: str | None = None


@dataclass
class SearchResult:
    results: list[dict] = field(default_factory=list)
    total_results: int = 0
    cost_usd: float = 0.0
    provider: str = ""
    cache_hit: bool = False


class SearchProvider(ABC):
    """Abstract base for all search providers."""

    @abstractmethod
    async def search(self, request: SearchRequest) -> SearchResult: ...

    @abstractmethod
    def estimate_cost(self, num_queries: int) -> float: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
