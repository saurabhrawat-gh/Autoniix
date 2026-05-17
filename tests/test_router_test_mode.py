"""Regression tests for the LLM router's test-mode short-circuit.

These guard the CI invariant that ``ENVIRONMENT_MODE=test`` resolves
every ``llm.*`` category through ``mock_llm`` with no DB or network
calls — the bug fixed in commit "fix(router): honor ENVIRONMENT_MODE
=test → mock_llm only" (May 2026).
"""
from __future__ import annotations

import asyncio

import pytest

from src.environment import clear_db_mode_override, set_db_mode_override
from src.llm.router import Router
from src.providers import boot  # noqa: F401  — registers all providers
from src.providers.llm.base import LLMRequest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestRouterTestMode:
    """The router must use mock_llm when env mode is 'test'."""

    def setup_method(self):
        clear_db_mode_override()
        set_db_mode_override("test")

    def teardown_method(self):
        clear_db_mode_override()

    @pytest.mark.parametrize("category", [
        "llm",
        "llm.research",
        "llm.script",
        "llm.factcheck",
        "llm.qc",
        "llm.ideation",
        "llm.hook",
        "llm.direction",
        "llm.emotion",
    ])
    def test_test_mode_resolves_to_mock_llm(self, category):
        router = Router()
        request = LLMRequest(
            messages=[
                {"role": "system", "content": "You write 1-sentence hooks."},
                {"role": "user", "content": "Topic: pasta water"},
            ],
            temperature=0.3,
            max_tokens=80,
            response_format="text",
        )
        result = _run(router.route(
            category=category,
            request=request,
            channel_id="EVAL",
            content_id="eval-test",
        ))
        assert result.provider == "mock_llm", (
            f"in test mode, {category} must resolve to mock_llm, "
            f"got {result.provider!r}"
        )
        assert result.cost_usd == 0.0
        assert result.content  # non-empty

    def test_test_mode_skips_db_lookups(self, monkeypatch):
        """The DB-bound helpers must never be awaited in test mode."""
        from src.llm import router as router_mod

        async def _explode(*_a, **_kw):
            raise AssertionError("DB lookup invoked in test mode")

        monkeypatch.setattr(router_mod, "_cap_for", _explode)
        monkeypatch.setattr(router_mod, "_spent_today", _explode)
        monkeypatch.setattr(router_mod, "_content_mode_for", _explode)
        monkeypatch.setattr(router_mod, "_db_chain_pairs", _explode)
        monkeypatch.setattr(router_mod, "_record_usage", _explode)

        router = Router()
        request = LLMRequest(
            messages=[
                {"role": "system", "content": "hook writer"},
                {"role": "user", "content": "Topic: anything"},
            ],
            temperature=0.3,
            max_tokens=40,
            response_format="text",
        )
        result = _run(router.route(
            category="llm.hook",
            request=request,
            channel_id="EVAL",
            content_id="eval-skip",
        ))
        assert result.provider == "mock_llm"

    def test_explicit_ladder_overrides_test_mode(self, monkeypatch):
        """Callers can still opt out by passing ``ladder=`` explicitly."""
        # Patch out the DB calls so the explicit-ladder path doesn't
        # actually hit a database when test_mode is True.
        from src.llm import router as router_mod

        async def _zero(*_a, **_kw):
            return 0.0

        async def _none(*_a, **_kw):
            return None

        async def _empty(*_a, **_kw):
            return []

        async def _noop(*_a, **_kw):
            return None

        monkeypatch.setattr(router_mod, "_cap_for", _zero)
        monkeypatch.setattr(router_mod, "_spent_today", _zero)
        monkeypatch.setattr(router_mod, "_content_mode_for", _none)
        monkeypatch.setattr(router_mod, "_db_chain_pairs", _empty)
        monkeypatch.setattr(router_mod, "_record_usage", _noop)

        router = Router()
        request = LLMRequest(
            messages=[{"role": "user", "content": "x"}],
            temperature=0.3,
            max_tokens=10,
            response_format="text",
        )
        result = _run(router.route(
            category="llm.hook",
            request=request,
            channel_id="EVAL",
            ladder=["mock_llm"],  # explicit
        ))
        assert result.provider == "mock_llm"


class TestOpenAIFailFast:
    """The openai provider must raise a clear error when api_key is empty."""

    def test_complete_raises_on_missing_api_key(self):
        from src.providers.llm.openai_provider import OpenAILLM

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
        from src.providers.llm.mock_provider import MockLLM

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
