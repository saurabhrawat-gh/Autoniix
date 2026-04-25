from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.image.base import ImageProvider, ImageRequest, ImageResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

DALLE_PRICING: dict[str, float] = {
    "1024x1024:standard": 0.04,
    "1024x1024:hd": 0.08,
    "1792x1024:standard": 0.08,
    "1792x1024:hd": 0.12,
    "1024x1792:standard": 0.08,
    "1024x1792:hd": 0.12,
}


class DALLEProvider(ImageProvider):
    BASE_URL = "https://api.openai.com/v1/images/generations"

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        if not self.api_key:
            logger.warning("dalle.no_api_key")

    async def generate(self, request: ImageRequest) -> ImageResult:
        body = {
            "model": "dall-e-3",
            "prompt": request.prompt,
            "n": 1,  # DALL-E 3 only supports n=1
            "size": request.size,
            "quality": request.quality,
            "style": request.style,
        }

        images: list[dict] = []
        total_cost = 0.0

        for _ in range(request.n):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

            for img in data.get("data", []):
                images.append(
                    {
                        "url": img.get("url", ""),
                        "revised_prompt": img.get("revised_prompt", ""),
                    }
                )

            cost_per = self.estimate_cost(1, request.quality, request.size)
            total_cost += cost_per

        logger.info(
            "dalle.generated",
            n=len(images),
            cost_usd=round(total_cost, 4),
        )

        return ImageResult(images=images, cost_usd=total_cost, provider="dalle")

    def estimate_cost(self, n: int, quality: str, size: str) -> float:
        key = f"{size}:{quality}"
        per_image = DALLE_PRICING.get(key, 0.04)
        return n * per_image

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "dalle"


ProviderRegistry.register("image", "dalle", DALLEProvider)
