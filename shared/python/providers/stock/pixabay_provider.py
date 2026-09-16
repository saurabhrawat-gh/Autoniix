from __future__ import annotations

import httpx
import structlog

from core.config import settings
from providers.registry import ProviderRegistry
from providers.stock.base import StockProvider, StockRequest, StockResult

logger = structlog.get_logger()

COST_PER_SEARCH = 0.0


class PixabayStock(StockProvider):
    BASE_URL = "https://pixabay.com/api"

    def __init__(self) -> None:
        self.api_key = settings.pixabay_api_key
        if not self.api_key:
            logger.warning("pixabay.no_api_key")

    async def search(self, request: StockRequest) -> StockResult:
        params = {
            "key": self.api_key,
            "q": request.query,
            "per_page": request.num_results,
            "video_type": request.media_type == "video" and "all" or None,
            "image_type": request.media_type == "image" and "photo" or None,
            "orientation": request.orientation,
            "min_video_duration": request.duration_min,
            "max_video_duration": request.duration_max,
        }

        params = {k: v for k, v in params.items() if v is not None}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        total = data.get("totalHits", 0)
        for item in data.get("hits", []):
            if request.media_type == "video":
                results.append(
                    {
                        "id": item.get("id"),
                        "url": item.get("videos", {}).get("medium", {}).get("url")
                        or item.get("videos", {}).get("large", {}).get("url"),
                        "thumbnail": item.get("picture_id"),
                        "duration": item.get("duration"),
                        "width": item.get("videos", {}).get("medium", {}).get("width"),
                        "height": item.get("videos", {}).get("medium", {}).get("height"),
                        "provider": "pixabay",
                    }
                )
            else:
                results.append(
                    {
                        "id": item.get("id"),
                        "url": item.get("largeImageURL") or item.get("webformatURL"),
                        "thumbnail": item.get("previewURL"),
                        "width": item.get("imageWidth"),
                        "height": item.get("imageHeight"),
                        "provider": "pixabay",
                    }
                )

        logger.info(
            "pixabay.searched",
            query=request.query,
            num_results=len(results),
            total=total,
        )

        return StockResult(
            results=results,
            total_results=total,
            cost_usd=COST_PER_SEARCH,
            provider="pixabay",
        )

    def estimate_cost(self, num_queries: int) -> float:
        return num_queries * COST_PER_SEARCH

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"key": self.api_key, "per_page": 3},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "pixabay"


ProviderRegistry.register("stock", "pixabay", PixabayStock)
