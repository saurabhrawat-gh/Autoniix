"""Unit tests for the token compression middleware (AE-520).

Covers:
- Context pruning (fast tier)
- Cache marker insertion for Anthropic
- Token estimation
- CompressionStats correctness
- Router integration (compression applied transparently)
- Graceful degradation when llmlingua is not installed
"""
from __future__ import annotations

import pytest

from src.providers.llm.base import LLMRequest
from src.llm.compressor import (
    CompressionStats,
    PromptCompressor,
    _add_cache_markers,
    _estimate_request_tokens,
    _estimate_tokens,
    _prune_context,
    compress_request,
)


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

class TestTokenEstimation:
    def test_estimate_tokens_basic(self):
        text = "Hello world, this is a test sentence."
        tokens = _estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)  # Tokens are fewer than characters.

    def test_estimate_tokens_empty(self):
        assert _estimate_tokens("") == 1  # Minimum 1 token.

    def test_estimate_tokens_model_hint(self):
        text = "x" * 1000
        gpt_tokens = _estimate_tokens(text, "gpt-4o")
        claude_tokens = _estimate_tokens(text, "claude-3-5-sonnet")
        # Different models have different char/token ratios.
        assert gpt_tokens != claude_tokens

    def test_estimate_request_tokens(self):
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            model="gpt-4o",
        )
        tokens = _estimate_request_tokens(req)
        assert tokens > 10
        assert tokens < 50

    def test_estimate_request_tokens_multimodal_skip(self):
        """Multimodal content with image parts should only count text."""
        req = LLMRequest(
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this image."},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                ]},
            ],
        )
        tokens = _estimate_request_tokens(req)
        assert tokens > 0
        # Should only count the text part, not the image.


# ---------------------------------------------------------------------------
# Context pruning (fast tier)
# ---------------------------------------------------------------------------

class TestContextPruning:
    def test_prune_collapses_whitespace(self):
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "Line 1\n\n\n\nLine 2\n\n\nLine 3"},
            ],
        )
        pruned = _prune_context(req, max_tokens=10000)
        user_content = pruned.messages[1]["content"]
        assert "\n\n\n" not in user_content
        assert "Line 1\n\nLine 2\n\nLine 3" in user_content

    def test_prune_preserves_system_prompt(self):
        sys_prompt = "You are a very important system prompt that must not be modified."
        req = LLMRequest(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": "Hello"},
            ],
        )
        pruned = _prune_context(req, max_tokens=10000)
        assert pruned.messages[0]["content"] == sys_prompt

    def test_prune_truncates_long_user_message(self):
        long_text = "word " * 5000  # ~5000 words, many tokens
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": long_text},
            ],
        )
        pruned = _prune_context(req, max_tokens=100)
        # The user message should be truncated.
        assert len(pruned.messages[1]["content"]) < len(long_text)

    def test_prune_does_not_mutate_original(self):
        original_content = "Original content that should not change."
        req = LLMRequest(
            messages=[{"role": "user", "content": original_content}],
        )
        _prune_context(req, max_tokens=10000)
        # Original request should be unchanged.
        assert req.messages[0]["content"] == original_content


# ---------------------------------------------------------------------------
# Cache markers
# ---------------------------------------------------------------------------

class TestCacheMarkers:
    def test_add_cache_markers_claude(self):
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "You are Claude."},
                {"role": "user", "content": "Hello"},
            ],
            model="claude-3-5-sonnet-20241022",
        )
        marked = _add_cache_markers(req)
        # System message should have cache_control.
        assert "cache_control" in marked.messages[0]
        assert marked.messages[0]["cache_control"] == {"type": "ephemeral"}
        # Last user message should have cache_control.
        assert "cache_control" in marked.messages[1]
        assert marked.messages[1]["cache_control"] == {"type": "ephemeral"}

    def test_add_cache_markers_non_anthropic_skipped(self):
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "You are GPT."},
                {"role": "user", "content": "Hello"},
            ],
            model="gpt-4o",
        )
        marked = _add_cache_markers(req)
        # OpenAI handles caching automatically — no markers needed.
        assert "cache_control" not in marked.messages[0]
        assert "cache_control" not in marked.messages[1]

    def test_add_cache_markers_no_system(self):
        req = LLMRequest(
            messages=[
                {"role": "user", "content": "Hello"},
            ],
            model="claude-3-5-sonnet-20241022",
        )
        marked = _add_cache_markers(req)
        # Only the last user message gets marked.
        assert "cache_control" in marked.messages[0]


# ---------------------------------------------------------------------------
# PromptCompressor
# ---------------------------------------------------------------------------

class TestPromptCompressor:
    @pytest.mark.asyncio
    async def test_off_tier_no_change(self):
        comp = PromptCompressor(tier="off")
        req = LLMRequest(
            messages=[{"role": "user", "content": "Hello world"}],
        )
        result, stats = await comp.compress(req)
        assert result is req  # Same object returned.
        assert stats.tier == "off"
        assert stats.savings_pct == 0.0

    @pytest.mark.asyncio
    async def test_fast_tier_prunes(self):
        comp = PromptCompressor(tier="fast", enable_cache_markers=False)
        # Need >= MIN_TOKENS_FOR_COMPRESSION (200) total tokens to trigger
        # the compression pipeline; otherwise compress() returns early.
        long_text = "Line 1\n\n\n\nLine 2\n\n\nLine 3 " + ("filler word " * 200)
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": long_text},
            ],
        )
        result, stats = await comp.compress(req)
        assert stats.tier == "fast"
        assert "prune" in stats.strategies_applied
        # Whitespace should be collapsed.
        assert "\n\n\n" not in result.messages[1]["content"]

    @pytest.mark.asyncio
    async def test_max_tier_includes_llmlingua_strategy(self):
        """Max tier should attempt llmlingua (gracefully skipped if not installed)."""
        comp = PromptCompressor(tier="max", enable_cache_markers=False)
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "This is a long prompt " + "with extra words " * 200},
            ],
        )
        result, stats = await comp.compress(req)
        assert stats.tier == "max"
        assert "prune" in stats.strategies_applied
        # llmlingua may or may not be installed — either way, no crash.
        assert stats.original_estimated_tokens > 0

    @pytest.mark.asyncio
    async def test_small_prompt_skipped(self):
        """Prompts below MIN_TOKENS_FOR_COMPRESSION should not be compressed."""
        comp = PromptCompressor(tier="max", enable_cache_markers=False)
        req = LLMRequest(
            messages=[{"role": "user", "content": "Hi"}],
        )
        result, stats = await comp.compress(req)
        # Should be unchanged since the prompt is tiny.
        assert stats.savings_pct == 0.0

    @pytest.mark.asyncio
    async def test_unknown_tier_falls_back_to_off(self):
        comp = PromptCompressor(tier="super_max")
        assert comp.tier == "off"


# ---------------------------------------------------------------------------
# CompressionStats
# ---------------------------------------------------------------------------

class TestCompressionStats:
    def test_reduction_ratio(self):
        stats = CompressionStats(
            original_estimated_tokens=1000,
            compressed_estimated_tokens=350,
            tier="max",
            strategies_applied=["prune", "llmlingua"],
        )
        assert stats.reduction_ratio == 0.35
        assert stats.savings_pct == 65.0

    def test_zero_original(self):
        stats = CompressionStats(
            original_estimated_tokens=0,
            compressed_estimated_tokens=0,
            tier="off",
        )
        assert stats.reduction_ratio == 1.0
        assert stats.savings_pct == 0.0


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

class TestCompressRequest:
    @pytest.mark.asyncio
    async def test_compress_request_off(self):
        req = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
        )
        result, stats = await compress_request(req, tier="off")
        assert result is req
        assert stats.tier == "off"

    @pytest.mark.asyncio
    async def test_compress_request_fast(self):
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "Test\n\n\n\nmessage"},
            ],
        )
        result, stats = await compress_request(req, tier="fast")
        assert stats.tier == "fast"
        assert stats.savings_pct >= 0


# ---------------------------------------------------------------------------
# Router integration smoke test
# ---------------------------------------------------------------------------

class TestRouterCompressionIntegration:
    """Verify the router applies compression transparently."""

    @pytest.mark.asyncio
    async def test_router_passes_compression_stats(self, monkeypatch):
        """When compression is enabled, the result should carry CompressionStats."""
        from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
        from src.providers.registry import ProviderRegistry
        from src.llm.router import Router

        class _FakeOK(LLMProvider):
            async def complete(self, request: LLMRequest) -> LLMResult:
                return LLMResult(
                    content='{"ok": true}', model="fake", tokens_in=10,
                    tokens_out=5, cost_usd=0.0001, provider="fake_ok", latency_ms=1,
                )
            def estimate_cost(self, *a, **kw): return 0.0
            async def health_check(self): return True
            def provider_name(self): return "fake_ok"
            def default_model(self): return "fake"
            def supported_models(self): return ["fake"]

        ProviderRegistry.register("llm", "fake_ok", _FakeOK)

        # Stub the DB helpers so the router doesn't need Postgres.
        async def _async_cap(*a, **kw):
            return 0.0
        async def _async_spent(*a, **kw):
            return 0.0
        async def _async_chain_pairs(*a, **kw):
            return []
        async def _async_record(*a, **kw):
            return None
        monkeypatch.setattr("src.llm.router._cap_for", _async_cap)
        monkeypatch.setattr("src.llm.router._spent_today", _async_spent)
        monkeypatch.setattr("src.llm.router._db_chain_pairs", _async_chain_pairs)
        monkeypatch.setattr("src.llm.router._record_usage", _async_record)

        router = Router()
        req = LLMRequest(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "Hello world " * 100},
            ],
        )
        result = await router.route(
            category="llm",
            request=req,
            ladder=["fake_ok"],
            compression_tier="fast",
        )
        # Result should carry compression stats.
        assert result.compression is not None
        assert result.compression.tier == "fast"
        assert "prune" in result.compression.strategies_applied

    @pytest.mark.asyncio
    async def test_router_off_tier_no_compression(self, monkeypatch):
        """When compression is off, result.compression should be None."""
        from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
        from src.providers.registry import ProviderRegistry
        from src.llm.router import Router

        class _FakeOK(LLMProvider):
            async def complete(self, request: LLMRequest) -> LLMResult:
                return LLMResult(
                    content='{"ok": true}', model="fake", tokens_in=10,
                    tokens_out=5, cost_usd=0.0001, provider="fake_ok", latency_ms=1,
                )
            def estimate_cost(self, *a, **kw): return 0.0
            async def health_check(self): return True
            def provider_name(self): return "fake_ok"
            def default_model(self): return "fake"
            def supported_models(self): return ["fake"]

        ProviderRegistry.register("llm", "fake_ok2", _FakeOK)

        async def _async_cap(*a, **kw):
            return 0.0
        async def _async_spent(*a, **kw):
            return 0.0
        async def _async_chain_pairs(*a, **kw):
            return []
        async def _async_record(*a, **kw):
            return None
        monkeypatch.setattr("src.llm.router._cap_for", _async_cap)
        monkeypatch.setattr("src.llm.router._spent_today", _async_spent)
        monkeypatch.setattr("src.llm.router._db_chain_pairs", _async_chain_pairs)
        monkeypatch.setattr("src.llm.router._record_usage", _async_record)

        router = Router()
        req = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
        )
        result = await router.route(
            category="llm",
            request=req,
            ladder=["fake_ok2"],
            compression_tier="off",
        )
        assert result.compression is None
