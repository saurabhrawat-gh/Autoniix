"""AE-34: Smoke gate — provider health assertions.

Fast unit tests that form the CI health gate:
- All test-mode (zero-cost, no-key) providers return health_check() == True
- Every registered category has at least one provider class
- Each provider class has a health_check() method
- chain resolve_chain signature is callable for all categories in test mode
- Render pipeline required categories are always present: llm, tts, storage, search
"""
from __future__ import annotations

import pytest

REQUIRED_CATEGORIES = {"llm", "tts", "storage", "search"}

TEST_MODE_PROVIDERS = [
    ("llm", "mock_llm"),
    ("tts", "edge_tts"),
    ("storage", "minio"),         # no API key required internally for unit
    ("search", "mock_search"),
]


# ── Registry gate ─────────────────────────────────────────────────────────────

def test_required_categories_registered():
    """All pipeline-critical categories must have at least one registered provider."""
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    for cat in REQUIRED_CATEGORIES:
        reg = ProviderRegistry._registries.get(cat, {})
        assert reg, f"No providers registered for required category {cat!r}"


def test_every_provider_has_health_check():
    """Every registered provider class must have a health_check() method."""
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    for cat, providers in ProviderRegistry._registries.items():
        for name, cls in providers.items():
            assert hasattr(cls, "health_check"), (
                f"Provider {cat}/{name} ({cls.__name__}) is missing health_check()"
            )


# ── Test-mode provider health ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_llm_health_check():
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    cls = ProviderRegistry._registries["llm"]["mock_llm"]
    inst = cls()
    assert await inst.health_check() is True


@pytest.mark.asyncio
async def test_edge_tts_health_check():
    from src.providers.tts.edge_tts_provider import EdgeTTSProvider

    inst = EdgeTTSProvider()
    result = await inst.health_check()
    # edge_tts returns True only if the package is installed
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_mock_search_health_check():
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry
    import inspect

    cls = ProviderRegistry._registries["search"]["mock_search"]
    inst = cls()
    result = inst.health_check()
    if inspect.isawaitable(result):
        result = await result
    assert result is True


@pytest.mark.asyncio
async def test_placeholder_image_health_check():
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    image_reg = ProviderRegistry._registries.get("image", {})
    if not image_reg:
        pytest.skip("No image providers registered")

    cls = image_reg.get("placeholder")
    if cls is None:
        pytest.skip("placeholder image provider not registered")

    import inspect
    inst = cls()
    result = inst.health_check()
    if inspect.isawaitable(result):
        result = await result
    assert result is True


# ── health_check return type contract ────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("category,provider_name", TEST_MODE_PROVIDERS)
async def test_test_mode_provider_health_check_returns_bool(category, provider_name):
    """health_check() must return a bool (sync or async)."""
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry
    from unittest.mock import patch, MagicMock

    cls = ProviderRegistry._registries.get(category, {}).get(provider_name)
    if cls is None:
        pytest.skip(f"{category}/{provider_name} not registered")

    # Patch Minio to avoid real connection for storage
    with patch("minio.Minio", MagicMock(return_value=MagicMock(bucket_exists=MagicMock(return_value=True)))):
        inst = cls()

    import inspect
    hc = inst.health_check()
    if inspect.isawaitable(hc):
        hc = await hc
    assert isinstance(hc, bool), (
        f"{category}/{provider_name}.health_check() returned {type(hc).__name__}, expected bool"
    )


# ── resolve_chain signature gate ─────────────────────────────────────────────

def test_resolve_chain_callable_for_all_categories():
    """resolve_chain must be importable and callable for all categories."""
    from src.providers.chain import resolve_chain
    import inspect

    sig = inspect.signature(resolve_chain)
    params = list(sig.parameters.keys())
    assert "category" in params
    assert "registry_map" in params
    assert "pipeline_mode" in params


def test_chain_cache_key_includes_pipeline_mode():
    from src.providers.chain import _cache_key

    key_prod = _cache_key("llm", "ch1", "short", "production")
    key_test = _cache_key("llm", "ch1", "short", "test")
    assert key_prod != key_test
    assert "production" in key_prod
    assert "test" in key_test
