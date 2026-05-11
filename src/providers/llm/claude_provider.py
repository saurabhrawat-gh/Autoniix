from __future__ import annotations

import time

import httpx
import structlog

from src.config import settings
from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-5-sonnet-20241022": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-5-haiku-20241022": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
}


class ClaudeLLM(LLMProvider):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self) -> None:
        self.api_key = settings.anthropic_api_key
        if not self.api_key:
            logger.warning("claude.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or self.default_model()
        start = time.monotonic()

        # Separate system from user/assistant messages
        system_text = ""
        messages = []
        for msg in request.messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Ensure alternating user/assistant (Claude requirement)
        if not messages or messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "Please proceed."})

        body: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system_text:
            body["system"] = system_text

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.BASE_URL, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        # Extract content
        content_blocks = data.get("content", [])
        content = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        # Extract usage
        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
        cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "claude.completed",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
            latency_ms=latency,
        )

        return LLMResult(
            content=content,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            provider="claude",
            latency_ms=latency,
            finish_reason=data.get("stop_reason", "end_turn"),
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.API_VERSION,
                    },
                )
                # 405 Method Not Allowed means the API is up
                return resp.status_code in (200, 405)
        except Exception:
            return False

    def provider_name(self) -> str:
        return "claude"

    def default_model(self) -> str:
        return settings.llm_claude_model

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


ProviderRegistry.register("llm", "claude", ClaudeLLM)
ProviderRegistry.register("llm.script", "claude", ClaudeLLM)
