from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.registry import ProviderRegistry
from src.providers.search.base import SearchProvider, SearchRequest, SearchResult

logger = structlog.get_logger()


class SerpAPISearch(SearchProvider):
    BASE_URL = "https://serpapi.com/search"
    COST_PER_QUERY = 0.01  # ~$50 / 5000 queries on Basic plan

    def __init__(self) -> None:
        self.api_key = settings.serpapi_key
        if not self.api_key:
            logger.warning("serpapi.no_api_key")

    async def search(self, request: SearchRequest) -> SearchResult:
        params = {
            "q": request.query,
            "api_key": self.api_key,
            "num": request.num_results,
            "engine": "google",
        }
        if request.search_type == "video":
            params["tbm"] = "vid"
        elif request.search_type == "news":
            params["tbm"] = "nws"
        if request.domain_filter:
            params["q"] = f"site:{request.domain_filter} {request.query}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        organic = data.get("organic_results", [])
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "position": r.get("position", 0),
            }
            for r in organic
        ]

        logger.info(
            "serpapi.searched",
            query=request.query[:60],
            results=len(results),
        )

        return SearchResult(
            results=results,
            total_results=len(results),
            cost_usd=self.COST_PER_QUERY,
            provider="serpapi",
        )

    def estimate_cost(self, num_queries: int) -> float:
        return num_queries * self.COST_PER_QUERY

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}?q=test&api_key={self.api_key}&num=1&engine=google"
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "serpapi"


ProviderRegistry.register("search", "serpapi", SerpAPISearch)
