from __future__ import annotations

import time

import httpx
import structlog

from src.config import settings
from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()

PRICING: dict[str, dict[str, float]] = {
    # Gemini 2.5 Flash family (current flagship)
    "gemini-2.5-flash": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gemini-2.5-flash-exp": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    # Gemini 2.0 Flash family (previous generation)
    "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    "gemini-2.0-flash-exp": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    # Gemini 1.5 Pro family (balanced quality)
    "gemini-1.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
    "gemini-1.5-pro-002": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
    # Gemini 1.5 Flash family (fast, budget)
    "gemini-1.5-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
    "gemini-1.5-flash-002": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
}


class GeminiLLM(LLMProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self) -> None:
        self.api_key = settings.google_ai_api_key
        if not self.api_key:
            logger.warning("gemini.no_api_key")

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or self.default_model()
        start = time.monotonic()

        # Convert OpenAI-style messages to Gemini format
        system_instruction = None
        contents = []
        for msg in request.messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        body: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if request.response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = f"{self.BASE_URL}/{model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            data = response.json()

        # Extract content
        candidates = data.get("candidates", [])
        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = parts[0].get("text", "") if parts else ""

        # Extract usage
        usage = data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", 0)
        tokens_out = usage.get("candidatesTokenCount", 0)
        pricing = PRICING.get(model, PRICING["gemini-2.5-flash"])
        cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "gemini.completed",
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
            provider="gemini",
            latency_ms=latency,
            finish_reason=candidates[0].get("finishReason", "STOP") if candidates else "STOP",
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        model = model or self.default_model()
        pricing = PRICING.get(model, PRICING["gemini-2.5-flash"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

    async def health_check(self) -> bool:
        try:
            url = f"{self.BASE_URL}?key={self.api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "gemini"

    def default_model(self) -> str:
        return settings.llm_gemini_model

    def supported_models(self) -> list[str]:
        return list(PRICING.keys())


ProviderRegistry.register("llm", "gemini", GeminiLLM)
ProviderRegistry.register("llm.research", "gemini", GeminiLLM)
ProviderRegistry.register("llm.qc", "gemini", GeminiLLM)
