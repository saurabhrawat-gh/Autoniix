"""Unit tests for ProviderRegistry.get(), FallbackProvider, EnvBackend,
and chain cache-invalidation helpers.

AE-315 — no real network calls; DB / flag / secret calls are mocked.
Run with: pytest tests/ -k providers
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.providers import chain as chain_mod
from src.providers.chain import FallbackProvider, NoProviderConfigured
from src.providers.registry import ProviderRegistry
from src.providers.secrets import EnvBackend


# ── Fake providers ────────────────────────────────────────────────────────────

class _FakeLLMProvider:
    """Minimal provider stand-in — sync and async methods."""

    def generate(self, prompt: str) -> str:
        return f"response:{prompt}"

    async def agenerate(self, prompt: str) -> str:
        return f"async-response:{prompt}"


class _BrokenProvider:
    """Provider that always raises on every method call."""

    def generate(self, *args, **kwargs):
        raise RuntimeError("broken")

    async def agenerate(self, *args, **kwargs):
        raise RuntimeError("broken-async")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_registry():
    """Clean ProviderRegistry class-level state before/after every test."""
    orig_registries = {k: dict(v) for k, v in ProviderRegistry._registries.items()}
    ProviderRegistry.reset()
    yield
    ProviderRegistry.reset()
    ProviderRegistry._registries.clear()
    ProviderRegistry._registries.update(orig_registries)


@pytest.fixture(autouse=True)
def _clear_chain_cache():
    chain_mod._chain_cache.clear()
    yield
    chain_mod._chain_cache.clear()


# ── ProviderRegistry.get() ────────────────────────────────────────────────────

class TestProviderRegistryGet:
    def setup_method(self):
        ProviderRegistry.register("llm", "fake", _FakeLLMProvider)

    def test_override_bypasses_db_chain(self):
        """Explicit override resolves directly from registry without DB."""
        p = ProviderRegistry.get("llm", override="fake")
        assert isinstance(p, _FakeLLMProvider)

    def test_override_unknown_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown llm provider"):
            ProviderRegistry.get("llm", override="nonexistent")

    def test_instance_cached_for_same_resolution_axes(self):
        p1 = ProviderRegistry.get("llm", override="fake")
        p2 = ProviderRegistry.get("llm", override="fake")
        assert p1 is p2

    def test_different_channel_ids_produce_different_instances(self):
        p1 = ProviderRegistry.get("llm", override="fake", channel_id="ch1")
        p2 = ProviderRegistry.get("llm", override="fake", channel_id="ch2")
        assert p1 is not p2

    def test_db_chain_result_returned_directly(self):
        """When _try_db_chain returns a FallbackProvider, get() returns it."""
        fake_chain = FallbackProvider("llm", [_FakeLLMProvider()], ["primary"])
        with patch.object(ProviderRegistry, "_try_db_chain", return_value=fake_chain):
            result = ProviderRegistry.get("llm")
        assert result is fake_chain

    def test_db_chain_empty_sentinel_raises_no_provider_configured(self):
        """EMPTY_CHAIN sentinel from _try_db_chain → NoProviderConfigured."""
        with patch.object(ProviderRegistry, "_try_db_chain",
                          return_value=chain_mod.EMPTY_CHAIN):
            with pytest.raises(NoProviderConfigured) as exc_info:
                ProviderRegistry.get("llm", channel_id="ch1", content_mode="short")
        assert "llm" in str(exc_info.value)

    def test_db_unavailable_falls_back_to_env_var(self, monkeypatch):
        """When _try_db_chain returns None, resolve via env-var map (LLM_PROVIDER)."""
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        with patch.object(ProviderRegistry, "_try_db_chain", return_value=None):
            p = ProviderRegistry.get("llm")
        assert isinstance(p, _FakeLLMProvider)

    def test_no_db_and_empty_env_raises_no_provider_configured(self):
        """DB unavailable AND no LLM_PROVIDER set → NoProviderConfigured."""
        with patch.object(ProviderRegistry, "_try_db_chain", return_value=None):
            clean_env = {k: v for k, v in os.environ.items() if k != "LLM_PROVIDER"}
            with patch.dict(os.environ, clean_env, clear=True):
                with pytest.raises(NoProviderConfigured):
                    ProviderRegistry.get("llm")

    def test_list_providers_returns_registered_names(self):
        names = ProviderRegistry.list_providers("llm")
        assert "fake" in names

    def test_reset_clears_instance_cache(self):
        ProviderRegistry.get("llm", override="fake")
        assert ProviderRegistry._instances
        ProviderRegistry.reset()
        assert ProviderRegistry._instances == {}

    def test_unregistered_category_raises_no_provider_configured(self):
        """Category with nothing registered + DB unavailable → NoProviderConfigured."""
        with patch.object(ProviderRegistry, "_try_db_chain", return_value=None):
            clean_env = {k: v for k, v in os.environ.items() if k != "IMAGE_PROVIDER"}
            with patch.dict(os.environ, clean_env, clear=True):
                with pytest.raises(NoProviderConfigured):
                    ProviderRegistry.get("image")


# ── FallbackProvider ──────────────────────────────────────────────────────────

class TestFallbackProvider:
    def test_sync_delegates_to_first_member(self):
        fp = FallbackProvider("llm", [_FakeLLMProvider()], ["primary"])
        assert fp.generate("hello") == "response:hello"

    def test_sync_advances_to_second_when_first_fails(self):
        fp = FallbackProvider("llm", [_BrokenProvider(), _FakeLLMProvider()],
                               ["broken", "working"])
        assert fp.generate("hi") == "response:hi"

    def test_sync_raises_last_exception_when_all_fail(self):
        fp = FallbackProvider("llm", [_BrokenProvider(), _BrokenProvider()],
                               ["b1", "b2"])
        with pytest.raises(RuntimeError, match="broken"):
            fp.generate("x")

    def test_attribute_error_when_no_member_has_method(self):
        fp = FallbackProvider("llm", [_FakeLLMProvider()], ["p"])
        with pytest.raises(AttributeError):
            _ = fp.nonexistent_method

    @pytest.mark.asyncio
    async def test_async_delegates_to_first_member(self):
        fp = FallbackProvider("llm", [_FakeLLMProvider()], ["primary"])
        assert await fp.agenerate("hello") == "async-response:hello"

    @pytest.mark.asyncio
    async def test_async_advances_to_second_when_first_fails(self):
        fp = FallbackProvider("llm", [_BrokenProvider(), _FakeLLMProvider()],
                               ["broken", "working"])
        assert await fp.agenerate("hi") == "async-response:hi"

    @pytest.mark.asyncio
    async def test_async_raises_last_exception_when_all_fail(self):
        fp = FallbackProvider("llm", [_BrokenProvider(), _BrokenProvider()],
                               ["b1", "b2"])
        with pytest.raises(RuntimeError, match="broken-async"):
            await fp.agenerate("x")

    def test_members_property_returns_defensive_copy(self):
        p = _FakeLLMProvider()
        fp = FallbackProvider("llm", [p], ["primary"])
        members = fp.members
        assert members == [p]
        members.clear()
        assert fp.members == [p]

    def test_labels_property_returns_defensive_copy(self):
        fp = FallbackProvider("llm", [_FakeLLMProvider()], ["my-label"])
        labels = fp.labels
        assert labels == ["my-label"]
        labels.clear()
        assert fp.labels == ["my-label"]


# ── EnvBackend ────────────────────────────────────────────────────────────────

class TestEnvBackend:
    def test_get_reads_env_var_by_translated_path(self, monkeypatch):
        monkeypatch.setenv("PROVIDERS_LLM_OPENAI_API_KEY", "sk-test")
        backend = EnvBackend()
        result = backend.get("providers/llm/openai", "api_key")
        assert result == "sk-test"

    def test_get_returns_none_when_var_not_set(self):
        backend = EnvBackend()
        with patch.dict(os.environ, {}, clear=True):
            assert backend.get("nonexistent/path", "api_key") is None

    def test_put_raises_not_implemented(self):
        backend = EnvBackend()
        with pytest.raises(NotImplementedError):
            backend.put("some/path", "api_key", "secret-value")

    def test_health_always_returns_true(self):
        assert EnvBackend().health() is True

    def test_get_uses_uppercase_key_as_fallback_candidate(self, monkeypatch):
        """When path-translated var is absent, bare key.upper() is tried."""
        monkeypatch.setenv("API_KEY", "sk-bare")
        backend = EnvBackend()
        result = backend.get("some/path", "api_key")
        assert result == "sk-bare"


# ── Cache invalidation helpers ────────────────────────────────────────────────

class TestCacheInvalidation:
    def test_reset_chain_cache_clears_everything(self):
        chain_mod._chain_cache[("ch1", "short", "llm", "production")] = ("x", 9e9)
        chain_mod._chain_cache[("",    "",      "tts", "production")] = ("y", 9e9)
        chain_mod.reset_chain_cache()
        assert chain_mod._chain_cache == {}

    def test_invalidate_no_args_clears_all(self):
        chain_mod._chain_cache[("ch1", "short", "llm", "production")] = ("a", 9e9)
        chain_mod.invalidate()
        assert chain_mod._chain_cache == {}

    def test_invalidate_by_content_mode_drops_matching_only(self):
        chain_mod._chain_cache[("ch1", "short", "llm", "production")] = ("a", 9e9)
        chain_mod._chain_cache[("ch1", "long",  "llm", "production")] = ("b", 9e9)
        chain_mod._chain_cache[("ch1", "",      "llm", "production")] = ("c", 9e9)
        chain_mod.invalidate(content_mode="short")
        remaining_modes = {k[1] for k in chain_mod._chain_cache.keys()}
        assert "short" not in remaining_modes
        assert "long" in remaining_modes

    def test_invalidate_by_category_drops_matching_only(self):
        chain_mod._chain_cache[("ch1", "short", "llm", "production")]   = ("a", 9e9)
        chain_mod._chain_cache[("ch1", "short", "image", "production")] = ("b", 9e9)
        chain_mod.invalidate(category="llm")
        remaining_cats = {k[2] for k in chain_mod._chain_cache.keys()}
        assert "llm" not in remaining_cats
        assert "image" in remaining_cats


# ── Feature flag behaviour ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_flag_off_returns_none():
    """When the DB feature flag is disabled, resolve_chain returns None
    so callers fall back to env-var resolution without hitting the DB."""
    with patch.object(chain_mod, "_flag_enabled", new=AsyncMock(return_value=False)):
        result = await chain_mod.resolve_chain("llm", registry_map={})
    assert result is None


# ── Cache TTL hit ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_skips_db_entirely():
    """A valid (non-expired) cache entry is returned without any DB call."""
    key = chain_mod._cache_key("llm", "ch1", "short", "production")
    cached_fp = FallbackProvider("llm", [_FakeLLMProvider()], ["cached"])
    chain_mod._chain_cache[key] = (cached_fp, 9e9)  # far-future TTL

    flag_called = False

    async def _spy_flag() -> bool:
        nonlocal flag_called
        flag_called = True
        return True

    with patch.object(chain_mod, "_flag_enabled", new=AsyncMock(side_effect=_spy_flag)):
        result = await chain_mod.resolve_chain(
            "llm", registry_map={},
            channel_id="ch1", content_mode="short",
        )

    assert result is cached_fp
    assert not flag_called, "DB flag should not be checked on cache hit"
