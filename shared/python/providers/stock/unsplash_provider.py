from __future__ import annotations

import httpx
import structlog

from core.config import settings
from providers.stock.base import StockProvider, StockRequest, StockResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

COST_PER_SEARCH = 0.0


class UnsplashStock(StockProvider):
    BASE_URL = "https://api.unsplash.com"

    def __init__(self) -> None:
        self.api_key = settings.unsplash_api_key
        if not self.api_key:
            logger.warning("unsplash.no_api_key")

    async def search(self, request: StockRequest) -> StockResult:
        headers = {
            "Authorization": f"Client-ID {self.api_key}",
        }

        endpoint = "/search/photos" if request.media_type == "image" else None

        if not endpoint:
            return StockResult(
                results=[],
                total_results=0,
                cost_usd=0.0,
                provider="unsplash",
            )

        params = {
            "query": request.query,
            "per_page": request.num_results,
        }
        if request.orientation:
            params["orientation"] = request.orientation

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.BASE_URL}{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        total = data.get("total", 0)
        for item in data.get("results", []):
            results.append({
                "id": item.get("id"),
                "url": item.get("urls", {}).get("regular"),
                "thumbnail": item.get("urls", {}).get("thumb"),
                "width": item.get("width"),
                "height": item.get("height"),
                "provider": "unsplash",
            })

        logger.info(
            "unsplash.searched",
            query=request.query,
            num_results=len(results),
            total=total,
        )

        return StockResult(
            results=results,
            total_results=total,
            cost_usd=COST_PER_SEARCH,
            provider="unsplash",
        )

    def estimate_cost(self, num_queries: int) -> float:
        return num_queries * COST_PER_SEARCH

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search/photos",
                    headers={"Authorization": f"Client-ID {self.api_key}"},
                    params={"query": "test", "per_page": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "unsplash"


ProviderRegistry.register("stock", "unsplash", UnsplashStock)
