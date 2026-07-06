"""LLM router provider and mock tests."""
from __future__ import annotations

import asyncio

import pytest

from providers import boot  # noqa: F401  — registers all providers
from providers.llm.base import LLMRequest


def _run(coro):
    return asyncio.run(coro)


class TestOpenAIFailFast:
    """The openai provider must raise a clear error when api_key is empty."""

    def test_complete_raises_on_missing_api_key(self):
        from providers.llm.openai_provider import OpenAILLM

        provider = OpenAILLM()
        provider.api_key = ""  # simulate missing config

        request = LLMRequest(
            messages=[{"role": "user", "content": "x"}],
            temperature=0.3,
            max_tokens=10,
            response_format="text",
        )
        with pytest.raises(RuntimeError, match="api_key not configured|no api_key"):
            _run(provider.complete(request))


class TestMockTextResponse:
    """Mock text-format responses must echo the topic for prompt-eval."""

    def test_hook_text_response_includes_topic_words(self):
        from providers.llm.mock_provider import MockLLM

        provider = MockLLM()
        provider.api_key = ""  # force static path

        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": "You write 1-sentence YouTube hooks.",
                },
                {
                    "role": "user",
                    "content": (
                        "Topic: Why pasta water is the secret ingredient "
                        "most home cooks waste."
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=80,
            response_format="text",
        )
        result = _run(provider.complete(request))
        body = result.content.lower()
        assert "pasta" in body and "water" in body, (
            f"mock text response must echo the topic; got: {result.content!r}"
        )
        assert "as an ai" not in body
        assert 25 <= len(result.content) <= 240
