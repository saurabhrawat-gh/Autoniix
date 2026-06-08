from __future__ import annotations

import time

import httpx
import structlog

from src.config import settings
from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

# DeepSeek V3 (deepseek-chat):     $0.27/1M input,  $1.10/1M output
# DeepSeek R1 (deepseek-reasoner): $0.55/1M input,  $2.19/1M output
PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat":     {"input": 0.27 / 1_000_000, "output": 1.10 / 1_000_000},
    "deepseek-reasoner": {"input": 0.55 / 1_000_000, "output": 2.19 / 1_000_000},
}


class DeepSeekLLM(LLMProvider):
    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self) -> None:
        self.api_key = settings.deepseek_api_key
        if not self.api_key:
            logger.warning("deepseek.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        if not self.api_key:
            raise RuntimeError(
                "deepseek provider has no api_key configured. Set "
                "DEEPSEEK_API_KEY or remove 'deepseek' from the provider "
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
        pricing = PRICING.get(model, PRICING["deepseek-chat"])
        cost = (
            usage["prompt_tokens"] * pricing["input"]
            + usage["completion_tokens"] * pricing["output"]
        )
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "deepseek.completed",
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
            provider="deepseek",
            latency_ms=latency,
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def estimate_cost(
        self, tokens_in: int, tokens_out: int, model: str | None = None
    ) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["deepseek-chat"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "deepseek"

    def default_model(self) -> str:
        return settings.llm_deepseek_model

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


ProviderRegistry.register("llm",           "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.research",  "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.script",    "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.factcheck", "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.qc",        "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.ideation",  "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.hook",      "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.direction", "deepseek", DeepSeekLLM)
ProviderRegistry.register("llm.emotion",   "deepseek", DeepSeekLLM)
