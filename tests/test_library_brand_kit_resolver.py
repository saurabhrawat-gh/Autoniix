"""Unit tests for the brand kit resolver — AE-357."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services_api.brand.brand_kit_resolver import (
    bind_channel_brand_kit,
    resolve_brand_kit_for_channel,
)


@pytest.mark.asyncio
async def test_resolve_returns_empty_when_no_kit_bound(mock_pool):
    mock_pool.fetchrow.return_value = None
    out = await resolve_brand_kit_for_channel("CH_x")
    assert out == {}


@pytest.mark.asyncio
async def test_resolve_returns_empty_on_db_error(mock_pool):
    mock_pool.fetchrow.side_effect = RuntimeError("connection refused")
    out = await resolve_brand_kit_for_channel("CH_x")
    assert out == {}


@pytest.mark.asyncio
async def test_resolve_expands_asset_ids_to_urls(mock_pool):
    mock_pool.fetchrow.side_effect = [
        {
            "kit_id": 5,
            "name": "Beast Mode v2",
            "palette": {"primary": "#fff"},
            "logo_asset_ids": [10, 11],
            "font_asset_ids": [20],
            "lut_asset_id": 30,
            "intro_asset_id": None,
            "outro_asset_id": None,
            "voice_sample_id": None,
            "motion_presets": {},
        },
        {"storage_key": "dam/x/y/logo/10.png"},
        {"storage_key": "dam/x/y/logo/11.svg"},
        {"storage_key": "dam/x/y/font/20.woff2"},
        {"storage_key": "dam/x/y/lut/30.cube"},
    ]

    storage = MagicMock()
    storage.get_signed_url = AsyncMock(side_effect=lambda key: f"https://cdn.test/{key}")
    with patch("providers.registry.ProviderRegistry.get", return_value=storage):
        out = await resolve_brand_kit_for_channel("CH_x")

    assert out["kit_id"] == 5
    assert out["name"] == "Beast Mode v2"
    assert out["palette"] == {"primary": "#fff"}
    assert out["logos"] == [
        "https://cdn.test/dam/x/y/logo/10.png",
        "https://cdn.test/dam/x/y/logo/11.svg",
    ]
    assert out["fonts"] == ["https://cdn.test/dam/x/y/font/20.woff2"]
    assert out["lut"] == "https://cdn.test/dam/x/y/lut/30.cube"
    assert out["intro"] is None


@pytest.mark.asyncio
async def test_bind_rejects_unknown_kit(mock_pool):
    mock_pool.fetchval.return_value = None
    with pytest.raises(ValueError):
        await bind_channel_brand_kit("CH_x", 99999)


@pytest.mark.asyncio
async def test_bind_updates_channel_row(mock_pool):
    mock_pool.fetchval.return_value = 1
    mock_pool.execute.return_value = "UPDATE 1"
    updated = await bind_channel_brand_kit("CH_x", 5)
    assert updated is True
    sql = mock_pool.execute.await_args.args[0]
    assert "UPDATE channels" in sql
    assert "brand_kit_id" in sql


@pytest.mark.asyncio
async def test_unbind_passes_null(mock_pool):
    mock_pool.execute.return_value = "UPDATE 1"
    updated = await bind_channel_brand_kit("CH_x", None)
    assert updated is True
    assert mock_pool.fetchval.await_count == 0
