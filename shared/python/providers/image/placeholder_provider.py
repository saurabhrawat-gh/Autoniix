"""Placeholder Image Provider — free image generation for test mode.

Generates solid-color images with "TEST" overlay using Pillow.
No external API calls, no cost.

Cost: $0.00
"""

from __future__ import annotations

import io

import structlog
from PIL import Image, ImageDraw, ImageFont

from providers.image.base import ImageProvider, ImageRequest, ImageResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

TEST_COLORS = [
    (99, 102, 241),
    (139, 92, 246),
    (236, 72, 153),
    (59, 130, 246),
    (16, 185, 129),
    (245, 158, 11),
]


class PlaceholderImageProvider(ImageProvider):
    """Generate placeholder images locally with Pillow."""

    async def generate(self, request: ImageRequest) -> ImageResult:
        images = []
        for i in range(request.n):
            w, h = self._parse_size(request.size)
            img_bytes = self._create_placeholder(w, h, request.prompt, i)
            images.append(
                {
                    "url": f"data:image/png;base64,placeholder_{i}",
                    "revised_prompt": f"[TEST] {request.prompt[:100]}",
                    "bytes": None,
                    "_bytes": img_bytes,
                }
            )

        logger.info("placeholder.generated", n=len(images), size=request.size)

        return ImageResult(
            images=images,
            cost_usd=0.0,
            provider="placeholder",
        )

    def _create_placeholder(self, w: int, h: int, prompt: str, index: int) -> bytes:
        """Create a colored rectangle with TEST label and prompt text."""
        color = TEST_COLORS[(index + hash(prompt)) % len(TEST_COLORS)]
        img = Image.new("RGB", (w, h), color)
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(24, w // 15))
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(14, w // 30))
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        label = "TEST MODE"
        bbox = draw.textbbox((0, 0), label, font=font_large)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) / 2, h * 0.35), label, fill=(255, 255, 255), font=font_large)

        preview = prompt[:60] + ("..." if len(prompt) > 60 else "")
        bbox2 = draw.textbbox((0, 0), preview, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        draw.text(((w - tw2) / 2, h * 0.55), preview, fill=(255, 255, 255, 200), font=font_small)

        draw.rectangle([10, 10, 80, 30], fill=(0, 0, 0, 128))
        try:
            badge_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
        except (OSError, IOError):
            badge_font = ImageFont.load_default()
        draw.text((15, 12), "TEST", fill=(255, 255, 255), font=badge_font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _parse_size(size: str) -> tuple[int, int]:
        """Parse '1024x1024' → (1024, 1024)."""
        try:
            parts = size.lower().split("x")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 1024, 1024

    def estimate_cost(self, n: int, quality: str, size: str) -> float:
        return 0.0

    async def health_check(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "placeholder"


ProviderRegistry.register("image", "placeholder", PlaceholderImageProvider)
