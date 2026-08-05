from __future__ import annotations

import httpx
import structlog

from core.config import settings
from providers.image.base import ImageProvider, ImageRequest, ImageResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, float] = {
    "fal-ai/flux/schnell": 0.003,
    "fal-ai/flux/dev": 0.025,
    "fal-ai/flux/pro": 0.050,
}

_SIZE_MAP: dict[str, str] = {
    "1024x1024": "square_hd",
    "1024x576": "landscape_16_9",
    "1280x720": "landscape_16_9",
    "1024x768": "landscape_4_3",
    "768x1024": "portrait_4_3",
    "1024x1792": "portrait_16_9",
    "1792x1024": "landscape_16_9",
}
_DEFAULT_FAL_SIZE = "landscape_16_9"


class FalFluxProvider(ImageProvider):
    BASE_URL = "https://fal.run"

    def __init__(self) -> None:
        self.api_key = settings.falai_api_key
        self._model_standard = settings.falai_flux_model
        self._model_hd = settings.falai_flux_hd_model
        if not self.api_key:
            logger.warning("fal_flux.no_api_key")

    async def generate(self, request: ImageRequest) -> ImageResult:
        if not self.api_key:
            raise RuntimeError(
                "fal_flux provider has no api_key configured. Set "
                "FAL_AI_API_KEY or switch IMAGE_PROVIDER back to 'dalle'."
            )

        model = self._model_hd if request.quality == "hd" else self._model_standard

        fal_size = _SIZE_MAP.get(request.size, _DEFAULT_FAL_SIZE)
        steps = 4 if "schnell" in model else 28

        body = {
            "prompt": request.prompt,
            "image_size": fal_size,
            "num_inference_steps": steps,
            "num_images": 1,
            "enable_safety_checker": True,
            "output_format": "jpeg",
        }

        url = f"{self.BASE_URL}/{model}"
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        images: list[dict] = []
        total_cost = 0.0
        cost_per = PRICING.get(model, PRICING["fal-ai/flux/schnell"])

        for _ in range(request.n):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()

            for img in data.get("images", []):
                images.append(
                    {
                        "url": img.get("url", ""),
                        "revised_prompt": request.prompt,
                        "width": img.get("width", 0),
                        "height": img.get("height", 0),
                    }
                )
            total_cost += cost_per

        logger.info(
            "fal_flux.generated",
            model=model,
            quality=request.quality,
            n=len(images),
            size=fal_size,
            cost_usd=round(total_cost, 4),
        )

        return ImageResult(images=images, cost_usd=total_cost, provider="fal_flux")

    def estimate_cost(self, n: int, quality: str, size: str) -> float:
        model = self._model_hd if quality == "hd" else self._model_standard
        return n * PRICING.get(model, PRICING["fal-ai/flux/schnell"])

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://fal.run/fal-ai/flux/schnell",
                    headers={"Authorization": f"Key {self.api_key}"},
                )
                return resp.status_code in (200, 405, 422)
        except Exception:
            return False

    def provider_name(self) -> str:
        return "fal_flux"


ProviderRegistry.register("image", "fal_flux", FalFluxProvider)
