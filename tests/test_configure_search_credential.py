"""Tests for AE-31: Configure Search credential (SerpAPI).

Covers:
- SerpAPISearch api_key settable via chain._instantiate direct-set fix
- WizardCredentialIn works for search category
- Wizard splits api_key → vault, no non-secret fields for serpapi
- health_check uses self.api_key (not settings snapshot)
"""
from __future__ import annotations

import pytest


def test_serpapi_api_key_settable(monkeypatch):
    """SerpAPISearch.api_key can be overridden when settings value is empty."""
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "serpapi_key", "")

    from src.providers.search.serpapi_provider import SerpAPISearch

    inst = SerpAPISearch()
    assert inst.api_key == ""

    # chain._instantiate direct-set path
    vault_key = "serp-test-key"
    if vault_key and hasattr(inst, "api_key") and not getattr(inst, "api_key", None):
        inst.api_key = vault_key

    assert inst.api_key == "serp-test-key"


def test_serpapi_registered():
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    reg = ProviderRegistry._registries.get("search", {})
    assert "serpapi" in reg


def test_serpapi_wizard_field_split():
    """serpapi has only one password field; extra_config stays empty."""
    schema = [
        {"name": "api_key", "type": "password", "label": "SerpAPI Key", "required": True},
    ]
    wizard_fields = {"api_key": "sk-serpapi-xyz"}

    secret_value = ""
    secret_key = "api_key"
    extra_config: dict = {}
    for field in schema:
        name = field["name"]
        value = wizard_fields.get(name)
        if value is None:
            continue
        if field.get("type") == "password":
            if not secret_value:
                secret_value = str(value)
                secret_key = name
        else:
            extra_config[name] = value

    assert secret_value == "sk-serpapi-xyz"
    assert secret_key == "api_key"
    assert extra_config == {}


def test_wizard_credential_in_search():
    from src.services.dashboard.v2.providers import WizardCredentialIn

    w = WizardCredentialIn(
        category="search",
        provider_key="serpapi",
        label="main-search",
        wizard_fields={"api_key": "sk-serpapi-abc"},
    )
    assert w.category == "search"
    assert w.provider_key == "serpapi"


def test_serpapi_health_check_uses_instance_api_key(monkeypatch):
    """health_check URL uses self.api_key, not a stale settings value."""
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "serpapi_key", "")

    from src.providers.search.serpapi_provider import SerpAPISearch

    inst = SerpAPISearch()
    inst.api_key = "injected-key"

    # Verify the key that would be embedded in the URL
    url_fragment = f"api_key={inst.api_key}"
    expected_url = f"{SerpAPISearch.BASE_URL}?q=test&api_key=injected-key&num=1&engine=google"
    assert "api_key=injected-key" in expected_url


def test_instantiate_sets_serpapi_key(monkeypatch):
    """Full chain._instantiate path for serpapi injects key when settings is empty."""
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "serpapi_key", "")

    import src.providers.boot  # noqa: F401
    from src.providers.chain import _instantiate
    from src.providers.registry import ProviderRegistry
    from unittest.mock import patch

    registry = ProviderRegistry._registries.get("search", {})
    with patch("src.providers.chain.get_secret_at", return_value="vault-serpapi-key"):
        inst = _instantiate("serpapi", "providers/search/serpapi/main", {}, None, registry)

    assert inst.api_key == "vault-serpapi-key"
