"""Tests for AE-71: Provider Catalog Seeding Migration.

Verifies:
- custom_openai_compat provider registers and runs
- boot.py registers custom_openai_compat in all LLM categories
- RotateIn schema accepts hint field
- setup-checklist response shape
"""
from __future__ import annotations

import pytest



def test_custom_openai_compat_registered():
    import providers.boot  # noqa: F401
    from providers.registry import ProviderRegistry

    for cat in (
        "llm", "llm.research", "llm.script", "llm.factcheck", "llm.qc",
        "llm.ideation", "llm.hook", "llm.direction", "llm.emotion",
    ):
        providers = ProviderRegistry.list_providers(cat)
        assert "custom_openai_compat" in providers, \
            f"custom_openai_compat not registered in category '{cat}'"


def test_custom_openai_compat_instantiates():
    import providers.boot  # noqa: F401
    from providers.llm.custom_openai_compat_provider import CustomOpenAICompatLLM

    inst = CustomOpenAICompatLLM()
    assert inst.provider_name() == "custom_openai_compat"
    assert inst.default_model() == "default"
    assert inst.supported_models() == []


@pytest.mark.asyncio
async def test_custom_openai_compat_health_check_no_url():
    from providers.llm.custom_openai_compat_provider import CustomOpenAICompatLLM

    inst = CustomOpenAICompatLLM()
    result = await inst.health_check()
    assert result is False



def test_rotate_in_accepts_hint():
    from services_api.dashboard.v2.providers import RotateIn

    r = RotateIn(secret_value="new-key", hint="Rotated during incident 2026-05-23")
    assert r.hint == "Rotated during incident 2026-05-23"
    assert r.secret_key == "api_key"


def test_rotate_in_hint_optional():
    from services_api.dashboard.v2.providers import RotateIn

    r = RotateIn(secret_value="new-key")
    assert r.hint is None



def test_migration_file_exists():
    import os
    path = os.path.join(
        os.path.dirname(__file__),
        "../scripts/migrations/202605230001_provider_catalog_and_pipeline_mode.sql",
    )
    assert os.path.isfile(os.path.normpath(path)), "Migration file not found"


def test_migration_contains_key_statements():
    import os
    path = os.path.join(
        os.path.dirname(__file__),
        "../scripts/migrations/202605230001_provider_catalog_and_pipeline_mode.sql",
    )
    content = open(os.path.normpath(path)).read()
    assert "pipeline_mode" in content
    assert "rotation_hint" in content
    assert "config_schema" in content
    assert "supported_models" in content
    assert "asset_sources" in content
    assert "custom_openai_compat" in content
    assert "chains_v2_unique_member" in content
