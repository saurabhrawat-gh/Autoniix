"""Zhipu GLM provider (OpenAI-compatible).

Uses Zhipu AI's open BigModel API which speaks the OpenAI
`/v1/chat/completions` wire format, so the implementation mirrors
``OpenAILLM`` with a different ``BASE_URL`` and pricing table.

Docs:  https://open.bigmodel.cn/dev/api
Auth:  Bearer token in ``GLM_API_KEY`` (set by the chain resolver from
       the credential's vault path).
"""

from __future__ import annotations

import os
import time

import httpx
import structlog

from providers.llm.base import LLMProvider, LLMRequest, LLMResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, dict[str, float]] = {
    "glm-4-plus": {"input": 1.40 / 1_000_000, "output": 1.40 / 1_000_000},
    "glm-4-air": {"input": 0.50 / 1_000_000, "output": 0.50 / 1_000_000},
    "glm-4-airx": {"input": 1.40 / 1_000_000, "output": 1.40 / 1_000_000},
    "glm-4-flash": {"input": 0.0, "output": 0.0},
    "glm-4-long": {"input": 0.14 / 1_000_000, "output": 0.14 / 1_000_000},
}


class GLMProvider(LLMProvider):
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    HEALTH_URL = "https://open.bigmodel.cn/api/paas/v4/models"

    def __init__(self) -> None:
        self.api_key = os.getenv("GLM_API_KEY", "")
        if not self.api_key:
            logger.warning("glm.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or self.default_model()
        start = time.monotonic()

        body: dict = {
            "model": model,
            "messages": request.messages,
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

        usage = data.get("usage", {})
        pricing = PRICING.get(model, PRICING["glm-4-air"])
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "glm.completed",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
            latency_ms=latency,
        )

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            provider="glm",
            latency_ms=latency,
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["glm-4-air"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.HEALTH_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code < 500
        except Exception:
            return False

    def provider_name(self) -> str:
        return "glm"

    def default_model(self) -> str:
        return os.getenv("LLM_GLM_MODEL", "glm-4-air")

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


for _cat in (
    "llm",
    "llm.research",
    "llm.script",
    "llm.factcheck",
    "llm.qc",
    "llm.ideation",
    "llm.hook",
    "llm.direction",
    "llm.emotion",
):
    ProviderRegistry.register(_cat, "glm", GLMProvider)
