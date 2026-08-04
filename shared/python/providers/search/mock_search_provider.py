"""Mock Search Provider — cached/free search for test mode.

Resolution order:
  1. Disk cache (tests/fixtures/search/<hash>.json) — instant, $0
  2. Wikipedia API fallback — completely free, no key needed
  3. Static results

Cost: $0.00
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx
import structlog

from providers.registry import ProviderRegistry
from providers.search.base import SearchProvider, SearchRequest, SearchResult

logger = structlog.get_logger()

_LOCAL_CACHE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "search"
CACHE_DIR = _LOCAL_CACHE if _LOCAL_CACHE.parent.exists() else Path("/tmp/mock_search_cache")


def _cache_key(query: str, search_type: str) -> str:
    raw = f"{query}:{search_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MockSearchProvider(SearchProvider):
    """Cached search provider for test mode."""

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def search(self, request: SearchRequest) -> SearchResult:
        key = _cache_key(request.query, request.search_type)
        cache_file = CACHE_DIR / f"{key}.json"

        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                logger.info("mock_search.cache_hit", key=key, query=request.query[:40])
                return SearchResult(
                    results=cached["results"],
                    total_results=len(cached["results"]),
                    cost_usd=0.0,
                    provider="mock_search",
                    cache_hit=True,
                )
            except (json.JSONDecodeError, KeyError):
                cache_file.unlink(missing_ok=True)

        try:
            results = await self._wikipedia_search(request.query, request.num_results)
            cache_file.write_text(json.dumps({
                "results": results,
                "query": request.query,
                "cached_at": time.time(),
            }))
            logger.info("mock_search.wikipedia_fallback", query=request.query[:40], results=len(results))
            return SearchResult(
                results=results,
                total_results=len(results),
                cost_usd=0.0,
                provider="mock_search_wikipedia",
            )
        except Exception as exc:
            logger.warning("mock_search.wikipedia_failed", error=str(exc))

        static = [
            {
                "title": f"[Test] Result for: {request.query[:50]}",
                "url": "https://en.wikipedia.org/wiki/Test",
                "snippet": "This is a mock search result generated in test mode.",
                "position": 1,
            }
        ]
        logger.info("mock_search.static_fallback", query=request.query[:40])
        return SearchResult(
            results=static,
            total_results=1,
            cost_usd=0.0,
            provider="mock_search_static",
        )

    async def _wikipedia_search(self, query: str, num_results: int) -> list[dict]:
        """Search Wikipedia API — completely free, no key needed."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": min(num_results, 10),
                    "format": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for i, item in enumerate(data.get("query", {}).get("search", []), 1):
            results.append({
                "title": item.get("title", ""),
                "url": f"https://en.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}",
                "snippet": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                "position": i,
            })
        return results

    def estimate_cost(self, num_queries: int) -> float:
        return 0.0

    async def health_check(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "mock_search"


ProviderRegistry.register("search", "mock_search", MockSearchProvider)
