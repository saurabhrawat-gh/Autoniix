from __future__ import annotations

import httpx
import structlog

from core.config import settings
from providers.stock.base import StockProvider, StockRequest, StockResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

COST_PER_SEARCH = 0.0


class PexelsStock(StockProvider):
    BASE_URL = "https://api.pexels.com/videos"

    def __init__(self) -> None:
        self.api_key = settings.pexels_api_key
        if not self.api_key:
            logger.warning("pexels.no_api_key")

    async def search(self, request: StockRequest) -> StockResult:
        headers = {
            "Authorization": self.api_key,
        }

        params = {
            "query": request.query,
            "per_page": request.num_results,
        }
        if request.orientation:
            params["orientation"] = request.orientation

        url = f"{self.BASE_URL}/search" if request.media_type == "video" else f"https://api.pexels.com/v1/search"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        total = data.get("total_results", 0)
        for item in data.get(request.media_type == "video" and "videos" or "photos", []):
            if request.media_type == "video":
                results.append({
                    "id": item.get("id"),
                    "url": item.get("video_files", [{}])[0].get("link") if item.get("video_files") else item.get("video_files"),
                    "thumbnail": item.get("image"),
                    "duration": item.get("duration"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "provider": "pexels",
                })
            else:
                results.append({
                    "id": item.get("id"),
                    "url": item.get("src", {}).get("original"),
                    "thumbnail": item.get("src", {}).get("large"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "provider": "pexels",
                })

        logger.info(
            "pexels.searched",
            query=request.query,
            num_results=len(results),
            total=total,
        )

        return StockResult(
            results=results,
            total_results=total,
            cost_usd=COST_PER_SEARCH,
            provider="pexels",
        )

    def estimate_cost(self, num_queries: int) -> float:
        return num_queries * COST_PER_SEARCH

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/popular",
                    headers={"Authorization": self.api_key},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "pexels"


ProviderRegistry.register("stock", "pexels", PexelsStock)
