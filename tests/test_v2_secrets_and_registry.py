"""Smoke tests for Phase 0+ infrastructure.

These tests do not require a running database — they only exercise pure
Python paths: the env-backed secrets resolver and the registry's graceful
fallback when the DB chain is unreachable.
"""

from __future__ import annotations

from providers.secrets import EnvBackend, get_secret_at, reset_cache


def test_env_backend_reads_path_to_env_var(monkeypatch):
    monkeypatch.setenv("PROVIDERS_LLM_OPENAI_DEFAULT_API_KEY", "sk-test-123")
    backend = EnvBackend()
    val = backend.get("providers/llm/openai/default", "api_key")
    assert val == "sk-test-123"


def test_env_backend_uppercase_fallback(monkeypatch):
    monkeypatch.setenv("API_KEY", "fallback-only")
    backend = EnvBackend()
    val = backend.get("nonexistent/path", "api_key")
    assert val == "fallback-only"


def test_get_secret_at_uses_env(monkeypatch):
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    monkeypatch.setenv("SECRETS_FALLBACK", "")
    monkeypatch.setenv("PROVIDERS_TTS_ELEVENLABS_LIVE_API_KEY", "el-secret")
    reset_cache()
    val = get_secret_at("providers/tts/elevenlabs/live", "api_key")
    assert val == "el-secret"


def test_registry_falls_back_to_env_when_no_db(monkeypatch):
    """ProviderRegistry.get must not crash when the DB chain is unreachable.

    We force ``providers.db_chain.enabled`` lookup to fail by pointing the
    pool at a bogus host; the registry should silently fall through to env.
    """
    from providers.registry import ProviderRegistry

    class _StubProvider:
        def __init__(self):
            self.name = "stub"

    ProviderRegistry._registries["llm"] = {"stub": _StubProvider}
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setattr("core.environment.is_test", lambda: False)
    ProviderRegistry.reset()

    inst = ProviderRegistry.get("llm")
    assert isinstance(inst, _StubProvider)
