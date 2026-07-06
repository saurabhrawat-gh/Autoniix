from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field

import httpx
import structlog

from core.config import settings
from providers.llm.base import LLMProvider, LLMRequest, LLMResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
}


@dataclass
class VisionRequest(LLMRequest):
    """LLM request that can include images."""
    image_urls: list[str] = field(default_factory=list)
    image_bytes_list: list[bytes] = field(default_factory=list)


class OpenAIVisionLLM(LLMProvider):
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        if not self.api_key:
            logger.warning("openai_vision.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or self.default_model()
        start = time.monotonic()

        messages = []
        for msg in request.messages:
            if msg["role"] == "system":
                messages.append(msg)
            elif msg["role"] == "user":
                content_parts = [{"type": "text", "text": msg["content"]}]

                if isinstance(request, VisionRequest):
                    for url in request.image_urls:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": url, "detail": "high"},
                        })
                    for img_bytes in request.image_bytes_list:
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                        })

                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append(msg)

        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        usage = data["usage"]
        pricing = PRICING.get(model, PRICING["gpt-4o"])
        cost = usage["prompt_tokens"] * pricing["input"] + usage["completion_tokens"] * pricing["output"]
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "openai_vision.completed",
            model=model,
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            cost_usd=round(cost, 6),
            latency_ms=latency,
        )

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            cost_usd=cost,
            provider="openai_vision",
            latency_ms=latency,
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["gpt-4o"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

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
        return "openai_vision"

    def default_model(self) -> str:
        return "gpt-4o"

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


ProviderRegistry.register("llm.vision", "openai", OpenAIVisionLLM)
