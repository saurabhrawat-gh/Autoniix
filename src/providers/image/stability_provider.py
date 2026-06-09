from __future__ import annotations

import httpx
import structlog

from src.config import settings
from src.providers.image.base import ImageProvider, ImageRequest, ImageResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

# Stability AI pricing: ~$0.04 per image for SDXL
COST_PER_IMAGE = 0.04


class StabilityAI(ImageProvider):
    BASE_URL = "https://api.stability.ai/v1/generation"

    def __init__(self) -> None:
        self.api_key = settings.stability_api_key
        if not self.api_key:
            logger.warning("stability.no_api_key")

    async def generate(self, request: ImageRequest) -> ImageResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Parse size (e.g., "1024x1024" -> width=1024, height=1024)
        width, height = map(int, request.size.split("x"))

        body = {
            "text_prompts": [{"text": request.prompt}],
            "cfg_scale": 7,
            "height": height,
            "width": width,
            "samples": request.n,
            "steps": 30,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        images = []
        for artifact in data.get("artifacts", []):
            import base64
            images.append({
                "url": f"data:image/png;base64,{artifact['base64']}",
                "revised_prompt": request.prompt,
            })

        cost = request.n * COST_PER_IMAGE

        logger.info(
            "stability.generated",
            prompt=request.prompt,
            num_images=len(images),
            cost_usd=round(cost, 4),
        )

        return ImageResult(
            images=images,
            cost_usd=cost,
            provider="stability",
        )

    def estimate_cost(self, n: int, quality: str, size: str) -> float:
        return n * COST_PER_IMAGE

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.stability.ai/v1/user/balance",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "stability"


ProviderRegistry.register("image", "stability", StabilityAI)
