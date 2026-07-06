from __future__ import annotations

import time

import httpx
import structlog

from core.config import settings
from providers.llm.base import LLMProvider, LLMRequest, LLMResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4-turbo": {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-4-turbo-preview": {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "gpt-3.5-turbo-16k": {"input": 3.00 / 1_000_000, "output": 4.00 / 1_000_000},
    "o1-preview": {"input": 15.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "o1-mini": {"input": 3.00 / 1_000_000, "output": 12.00 / 1_000_000},
}


class OpenAILLM(LLMProvider):
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        if not self.api_key:
            logger.warning("openai.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        if not self.api_key:
            raise RuntimeError(
                "openai provider has no api_key configured. Set "
                "OPENAI_API_KEY or remove 'openai' from the provider "
                "ladder for this category."
            )

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

        usage = data["usage"]
        pricing = PRICING.get(model, PRICING["gpt-4o"])
        cost = (
            usage["prompt_tokens"] * pricing["input"]
            + usage["completion_tokens"] * pricing["output"]
        )
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "openai.completed",
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
            provider="openai",
            latency_ms=latency,
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def estimate_cost(
        self, tokens_in: int, tokens_out: int, model: str | None = None
    ) -> float:
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
        return "openai"

    def default_model(self) -> str:
        return settings.llm_openai_model

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


ProviderRegistry.register("llm", "openai", OpenAILLM)
ProviderRegistry.register("llm.research", "openai", OpenAILLM)
ProviderRegistry.register("llm.script", "openai", OpenAILLM)
ProviderRegistry.register("llm.factcheck", "openai", OpenAILLM)
ProviderRegistry.register("llm.qc", "openai", OpenAILLM)
ProviderRegistry.register("llm.ideation", "openai", OpenAILLM)
ProviderRegistry.register("llm.hook", "openai", OpenAILLM)
ProviderRegistry.register("llm.direction", "openai", OpenAILLM)
ProviderRegistry.register("llm.emotion", "openai", OpenAILLM)
