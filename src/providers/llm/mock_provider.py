"""Mock LLM Provider — cached responses for test mode.

Resolution order:
  1. Disk cache (tests/fixtures/llm/<hash>.json) — instant, $0
  2. GPT-4o-mini fallback — cheapest model, caches result for next run
  3. Static fallback JSON — if no API key available

Cost: $0.00 on cache hit, ~$0.001 on cache miss (GPT-4o-mini).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx
import structlog

from src.config import settings
from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

CACHE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm"


def _cache_key(messages: list[dict], model: str) -> str:
    """Deterministic hash of prompt for cache lookup."""
    raw = json.dumps(messages, sort_keys=True) + model
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MockLLM(LLMProvider):
    """Cached LLM for test mode. Checks disk cache first, falls back to GPT-4o-mini."""

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.api_key = settings.openai_api_key  # for fallback

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or "gpt-4o-mini"
        key = _cache_key(request.messages, model)
        cache_file = CACHE_DIR / f"{key}.json"

        # 1. Check disk cache
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                logger.info("mock_llm.cache_hit", key=key)
                return LLMResult(
                    content=cached["content"],
                    model=f"mock-cached-{model}",
                    tokens_in=cached.get("tokens_in", 0),
                    tokens_out=cached.get("tokens_out", 0),
                    cost_usd=0.0,
                    provider="mock_llm",
                    latency_ms=1,
                    finish_reason="stop",
                )
            except (json.JSONDecodeError, KeyError):
                cache_file.unlink(missing_ok=True)

        # 2. Fallback: call GPT-4o-mini if API key available
        if self.api_key:
            try:
                result = await self._call_cheap_model(request, model)
                # Cache the result
                cache_file.write_text(json.dumps({
                    "content": result.content,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "model": model,
                    "cached_at": time.time(),
                }))
                logger.info("mock_llm.cache_miss_called_api", key=key, cost=result.cost_usd)
                return result
            except Exception as exc:
                logger.warning("mock_llm.api_fallback_failed", error=str(exc))

        # 3. Static fallback — return generic JSON response
        logger.info("mock_llm.static_fallback", key=key)
        static_content = self._static_response(request)
        return LLMResult(
            content=static_content,
            model="mock-static",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            provider="mock_llm",
            latency_ms=0,
            finish_reason="stop",
        )

    async def _call_cheap_model(self, request: LLMRequest, model: str) -> LLMResult:
        """Call GPT-4o-mini as cheap fallback."""
        body: dict = {
            "model": "gpt-4o-mini",
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": min(request.max_tokens, 2000),
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data["usage"]
        cost = usage["prompt_tokens"] * 0.15e-6 + usage["completion_tokens"] * 0.60e-6
        latency = int((time.monotonic() - start) * 1000)

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model="gpt-4o-mini",
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            cost_usd=cost,
            provider="mock_llm",
            latency_ms=latency,
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def _static_response(self, request: LLMRequest) -> str:
        """Return a plausible static response based on whether JSON was requested."""
        if request.response_format == "json":
            return json.dumps({
                "result": "test_mock_response",
                "score": 8.0,
                "items": [],
                "summary": "This is a mock response generated in test mode.",
            })
        return "This is a mock response generated in test mode. The pipeline is working correctly but no real LLM was called."

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        return 0.0

    async def health_check(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "mock_llm"

    def default_model(self) -> str:
        return "mock-gpt-4o-mini"

    def supported_models(self) -> list[str]:
        return ["mock-gpt-4o-mini", "mock-cached", "mock-static"]


# Register for all LLM categories
ProviderRegistry.register("llm", "mock_llm", MockLLM)
ProviderRegistry.register("llm.research", "mock_llm", MockLLM)
ProviderRegistry.register("llm.script", "mock_llm", MockLLM)
ProviderRegistry.register("llm.factcheck", "mock_llm", MockLLM)
ProviderRegistry.register("llm.qc", "mock_llm", MockLLM)
ProviderRegistry.register("llm.ideation", "mock_llm", MockLLM)
ProviderRegistry.register("llm.hook", "mock_llm", MockLLM)
ProviderRegistry.register("llm.direction", "mock_llm", MockLLM)
ProviderRegistry.register("llm.emotion", "mock_llm", MockLLM)
