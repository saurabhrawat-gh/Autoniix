from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.stock.base import StockProvider, StockRequest, StockResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

# Kling AI pricing: ~$0.05 per video generation
COST_PER_SEARCH = 0.05


class KlingStock(StockProvider):
    BASE_URL = "https://api.klingai.com/v1"

    def __init__(self) -> None:
        self.api_key = settings.kling_api_key
        if not self.api_key:
            logger.warning("kling.no_api_key")

    async def search(self, request: StockRequest) -> StockResult:
        # Kling AI is primarily a generative AI, not a stock search
        # This is a placeholder implementation for future integration
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "prompt": request.query,
            "num_videos": request.num_results,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/videos/generate",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        total = data.get("total", 0)
        for item in data.get("videos", []):
            results.append({
                "id": item.get("id"),
                "url": item.get("url"),
                "thumbnail": item.get("thumbnail"),
                "duration": item.get("duration"),
                "provider": "kling",
            })

        logger.info(
            "kling.searched",
            query=request.query,
            num_results=len(results),
            total=total,
        )

        return StockResult(
            results=results,
            total_results=total,
            cost_usd=COST_PER_SEARCH * request.num_results,
            provider="kling",
        )

    def estimate_cost(self, num_queries: int) -> float:
        return num_queries * COST_PER_SEARCH

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "kling"


ProviderRegistry.register("stock", "kling", KlingStock)
