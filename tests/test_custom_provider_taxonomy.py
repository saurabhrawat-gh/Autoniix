"""Tests for the user-editable provider taxonomy (custom sections / categories /
providers) and the JSONB-string hardening that fixed the "Add credentials always
breaking" bug.

Pure unit tests — no DB required. They cover:
- _as_json: tolerates JSONB columns returned as raw strings (the SS10 root cause)
- _slugify: derives safe keys from human labels
- _default_config_schema: minimal api_key + model schema for custom providers
- KindIn / CategoryIn / MarketplaceProviderIn request models
- migration file presence + key statements
"""

from __future__ import annotations


def test_as_json_parses_string_list():
    from services_api.dashboard.v2.providers import _as_json

    assert _as_json('[{"name": "api_key"}]', []) == [{"name": "api_key"}]


def test_as_json_passes_through_real_list():
    from services_api.dashboard.v2.providers import _as_json

    val = [{"name": "model"}]
    assert _as_json(val, []) is val


def test_as_json_none_and_garbage_fall_back_to_default():
    from services_api.dashboard.v2.providers import _as_json

    assert _as_json(None, []) == []
    assert _as_json("not json", []) == []
    assert _as_json("", {"k": 1}) == {"k": 1}


def test_slugify_basic():
    from services_api.dashboard.v2.providers import _slugify

    assert _slugify("Avatar Generation") == "avatar_generation"
    assert _slugify("HeyGen!!") == "heygen"
    assert _slugify("Product   demo  avatars") == "product_demo_avatars"


def test_slugify_empty_falls_back():
    from services_api.dashboard.v2.providers import _slugify

    assert _slugify("   ") == "custom"
    assert _slugify("!!!") == "custom"


def test_slugify_respects_maxlen():
    from services_api.dashboard.v2.providers import _slugify

    assert len(_slugify("x" * 100, maxlen=20)) <= 20


def test_default_config_schema_with_key():
    from services_api.dashboard.v2.providers import _default_config_schema

    schema = _default_config_schema(True)
    names = [f["name"] for f in schema]
    assert "api_key" in names and "model" in names
    api = next(f for f in schema if f["name"] == "api_key")
    assert api["type"] == "password" and api["required"] is True


def test_default_config_schema_without_key():
    from services_api.dashboard.v2.providers import _default_config_schema

    schema = _default_config_schema(False)
    names = [f["name"] for f in schema]
    assert "api_key" not in names and "model" in names


def test_kind_in_defaults():
    from services_api.dashboard.v2.providers import KindIn

    k = KindIn(label="Avatar Generation")
    assert k.kind is None and k.icon is None


def test_category_in_requires_kind():
    from services_api.dashboard.v2.providers import CategoryIn

    c = CategoryIn(label="Product demo avatars", kind="avatar")
    assert c.kind == "avatar" and c.name is None


def test_marketplace_provider_in_defaults():
    from services_api.dashboard.v2.providers import MarketplaceProviderIn

    p = MarketplaceProviderIn(display_name="HeyGen", kind="avatar")
    assert p.requires_api_key is True
    assert p.has_free_tier is False
    assert p.supported_models == []


def test_taxonomy_migration_exists_and_has_key_statements():
    import os

    path = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "../scripts/migrations/202606020002_custom_provider_catalog.sql",
        )
    )
    assert os.path.isfile(path), "Custom taxonomy migration not found"
    content = open(path).read()
    assert "CREATE TABLE IF NOT EXISTS provider_kinds" in content
    assert "is_user_defined" in content
    assert "is_callable" in content
    assert "seed_builtin_provider_taxonomy" in content
