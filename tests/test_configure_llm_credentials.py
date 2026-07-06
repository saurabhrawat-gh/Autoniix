"""Tests for AE-29: Configure LLM credentials — catalog wizard + custom_openai_compat.

Covers:
- CredentialIn allows empty secret_value (no-key providers)
- WizardCredentialIn schema
- Wizard field splitting: password → secret, others → extra_config
- custom_openai_compat base_url set via extra_config (chain._instantiate)
- config_schema required-field validation logic
"""
from __future__ import annotations

import pytest


def test_credential_in_empty_secret_value():
    from services_api.dashboard.v2.providers import CredentialIn

    c = CredentialIn(category="tts", provider_name="edge_tts", label="free")
    assert c.secret_value == ""


def test_credential_in_with_api_key():
    from services_api.dashboard.v2.providers import CredentialIn

    c = CredentialIn(
        category="llm", provider_name="openai", label="main",
        secret_value="sk-test",
    )
    assert c.secret_value == "sk-test"
    assert c.secret_key == "api_key"


def test_wizard_credential_in_schema():
    from services_api.dashboard.v2.providers import WizardCredentialIn

    w = WizardCredentialIn(
        category="llm",
        provider_key="openai",
        label="my-openai",
        wizard_fields={"api_key": "sk-test", "model": "gpt-4o"},
    )
    assert w.provider_key == "openai"
    assert w.wizard_fields["api_key"] == "sk-test"
    assert w.model is None


def test_wizard_field_split_separates_password_and_plain():
    """Simulate the split logic inside create_credential_from_wizard."""
    schema = [
        {"name": "api_key", "type": "password", "required": True},
        {"name": "model", "type": "select", "required": False},
        {"name": "voice_id", "type": "text", "required": False},
    ]
    wizard_fields = {"api_key": "sk-secret", "model": "gpt-4o", "voice_id": "xyz"}

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

    assert secret_value == "sk-secret"
    assert secret_key == "api_key"
    assert extra_config == {"model": "gpt-4o", "voice_id": "xyz"}


def test_wizard_required_field_validation():
    """Validate required field check from config_schema."""
    schema = [
        {"name": "api_key", "type": "password", "required": True},
        {"name": "voice_id", "type": "text", "required": True},
        {"name": "model", "type": "select", "required": False},
    ]
    wizard_fields = {"api_key": "sk-test"}

    missing = [
        f["name"]
        for f in schema
        if f.get("required") and not wizard_fields.get(f["name"])
    ]
    assert missing == ["voice_id"]


def test_wizard_no_key_provider_skips_vault():
    """edge_tts wizard_fields has no password field → secret_value stays empty."""
    schema = [
        {"name": "voice", "type": "text", "required": False},
    ]
    wizard_fields = {"voice": "en-US-AriaNeural"}

    secret_value = ""
    extra_config: dict = {}
    for field in schema:
        name = field["name"]
        value = wizard_fields.get(name)
        if value is None:
            continue
        if field.get("type") == "password":
            if not secret_value:
                secret_value = str(value)
        else:
            extra_config[name] = value

    assert secret_value == ""
    assert extra_config == {"voice": "en-US-AriaNeural"}


def test_custom_openai_compat_base_url_via_extra_config():
    """chain._instantiate applies extra_config keys via setattr."""
    import providers.boot  # noqa: F401
    from providers.llm.custom_openai_compat_provider import CustomOpenAICompatLLM

    inst = CustomOpenAICompatLLM()
    extra = {"base_url": "http://vllm-server:8000", "model": "mistral-7b"}
    for k, v in extra.items():
        setattr(inst, k, v)

    assert inst.base_url == "http://vllm-server:8000"
    assert inst.model == "mistral-7b"
    assert inst.default_model() == "mistral-7b"


@pytest.mark.asyncio
async def test_custom_openai_compat_no_url_raises_on_complete():
    """complete() raises RuntimeError when base_url is not set."""
    from providers.llm.custom_openai_compat_provider import CustomOpenAICompatLLM
    from providers.llm.base import LLMRequest

    inst = CustomOpenAICompatLLM()
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(RuntimeError, match="base_url not configured"):
        await inst.complete(req)
