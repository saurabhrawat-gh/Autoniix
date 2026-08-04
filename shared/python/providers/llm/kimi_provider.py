"""Moonshot Kimi provider (OpenAI-compatible).

Moonshot AI's API mirrors OpenAI's `/v1/chat/completions` schema, so
this provider mirrors ``OpenAILLM`` with a different base URL +
pricing.

Docs:  https://platform.moonshot.cn/docs/api
Auth:  Bearer token in ``KIMI_API_KEY`` (injected by the chain
       resolver from the credential's vault path).
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
    "moonshot-v1-8k":   {"input": 1.68 / 1_000_000, "output": 1.68 / 1_000_000},
    "moonshot-v1-32k":  {"input": 3.36 / 1_000_000, "output": 3.36 / 1_000_000},
    "moonshot-v1-128k": {"input": 8.40 / 1_000_000, "output": 8.40 / 1_000_000},
    "moonshot-v1-auto": {"input": 1.68 / 1_000_000, "output": 1.68 / 1_000_000},
}


class KimiProvider(LLMProvider):
    BASE_URL = "https://api.moonshot.cn/v1/chat/completions"
    HEALTH_URL = "https://api.moonshot.cn/v1/models"

    def __init__(self) -> None:
        self.api_key = os.getenv("KIMI_API_KEY", "")
        if not self.api_key:
            logger.warning("kimi.no_api_key")

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
        pricing = PRICING.get(model, PRICING["moonshot-v1-8k"])
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "kimi.completed",
            model=model, tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=round(cost, 6), latency_ms=latency,
        )

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            provider="kimi",
            latency_ms=latency,
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    def estimate_cost(
        self, tokens_in: int, tokens_out: int, model: str | None = None
    ) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["moonshot-v1-8k"])
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
        return "kimi"

    def default_model(self) -> str:
        return os.getenv("LLM_KIMI_MODEL", "moonshot-v1-auto")

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


for _cat in (
    "llm", "llm.research", "llm.script", "llm.factcheck", "llm.qc",
    "llm.ideation", "llm.hook", "llm.direction", "llm.emotion",
):
    ProviderRegistry.register(_cat, "kimi", KimiProvider)
