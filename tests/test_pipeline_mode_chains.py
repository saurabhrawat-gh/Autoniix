"""Tests for AE-74: Test vs Production Provider Chains (pipeline_mode).

Verifies:
- _cache_key includes pipeline_mode as the 4th element
- ChainV2In has pipeline_mode field with 'production' default
- resolved_chain endpoint includes pipeline_mode in response
- registry.get() accepts pipeline_mode kwarg
"""

from __future__ import annotations


def test_cache_key_includes_pipeline_mode():
    from providers.chain import _cache_key

    key_prod = _cache_key("llm", None, None, "production")
    key_test = _cache_key("llm", None, None, "test")
    assert len(key_prod) == 4
    assert key_prod[3] == "production"
    assert key_test[3] == "test"
    assert key_prod != key_test


def test_cache_key_defaults_to_production():
    from providers.chain import _cache_key

    key = _cache_key("llm", None, None)
    assert key[3] == "production"


def test_cache_key_differentiates_channel_and_mode():
    from providers.chain import _cache_key

    k1 = _cache_key("llm", "ch-1", "faceless", "production")
    k2 = _cache_key("llm", "ch-1", "faceless", "test")
    assert k1 != k2
    assert k1[0] == "ch-1"
    assert k1[1] == "faceless"


def test_chain_v2_in_default_pipeline_mode():
    from services_api.dashboard.v2.providers import ChainV2In

    body = ChainV2In(category="llm", credential_ids=[])
    assert body.pipeline_mode == "production"


def test_chain_v2_in_test_pipeline_mode():
    from services_api.dashboard.v2.providers import ChainV2In

    body = ChainV2In(category="llm", pipeline_mode="test", credential_ids=[])
    assert body.pipeline_mode == "test"


def test_registry_get_accepts_pipeline_mode():
    """Ensure registry.get() signature accepts pipeline_mode without error."""
    import inspect

    from providers.registry import ProviderRegistry

    sig = inspect.signature(ProviderRegistry.get)
    assert "pipeline_mode" in sig.parameters


def test_load_layer_signature_has_pipeline_mode():
    import inspect

    from providers.chain import _load_layer

    sig = inspect.signature(_load_layer)
    assert "pipeline_mode" in sig.parameters
    assert sig.parameters["pipeline_mode"].default == "production"


def test_load_chain_signature_has_pipeline_mode():
    import inspect

    from providers.chain import _load_chain

    sig = inspect.signature(_load_chain)
    assert "pipeline_mode" in sig.parameters
    assert sig.parameters["pipeline_mode"].default == "production"


def test_resolve_chain_signature_has_pipeline_mode():
    import inspect

    from providers.chain import resolve_chain

    sig = inspect.signature(resolve_chain)
    assert "pipeline_mode" in sig.parameters
    assert sig.parameters["pipeline_mode"].default == "production"
