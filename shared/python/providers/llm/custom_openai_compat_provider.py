"""Custom OpenAI-compatible provider.

Allows connecting any third-party LLM that exposes the OpenAI
``/v1/chat/completions`` wire format (e.g. local vLLM, LM Studio,
Together AI, Fireworks AI, Mistral, DeepSeek, etc.).

The credential's ``extra_config`` **must** contain ``base_url``.  An optional
``model`` column on the credential row pins the model; if absent the request
model or ``DEFAULT_MODEL`` is used.

Registered as ``custom_openai_compat`` in every LLM sub-category so it can
be selected from the provider credential wizard.
"""

from __future__ import annotations

import time

import httpx
import structlog

from providers.llm.base import LLMProvider, LLMRequest, LLMResult
from providers.registry import ProviderRegistry

logger = structlog.get_logger()

DEFAULT_MODEL = "default"


class CustomOpenAICompatLLM(LLMProvider):
    def __init__(self) -> None:
        self.api_key: str = ""
        self.base_url: str = ""
        self.model: str | None = None

    async def complete(self, request: LLMRequest) -> LLMResult:
        if not self.base_url:
            raise RuntimeError(
                "custom_openai_compat: base_url not configured. Set it in extra_config when creating the credential."
            )
        model = request.model or self.model or DEFAULT_MODEL
        start = time.monotonic()

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body: dict = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        latency = int((time.monotonic() - start) * 1000)

        logger.info(
            "custom_openai_compat.completed",
            base_url=self.base_url,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
        )

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            provider="custom_openai_compat",
            latency_ms=latency,
            finish_reason=data["choices"][0].get("finish_reason"),
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        return 0.0

    async def health_check(self) -> bool:
        if not self.base_url:
            return False
        try:
            url = self.base_url.rstrip("/") + "/v1/models"
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "custom_openai_compat"

    def default_model(self) -> str:
        return self.model or DEFAULT_MODEL

    def supported_models(self) -> list[str]:
        return []


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
    ProviderRegistry.register(_cat, "custom_openai_compat", CustomOpenAICompatLLM)
