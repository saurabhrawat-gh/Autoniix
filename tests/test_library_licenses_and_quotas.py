"""Unit tests for license catalogue / expiry + storage quotas — AE-363, AE-364."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services_api.dashboard.v2.library_licenses import (
    _catalogue_fallback,
    license_catalogue,
    licenses_audit,
    licenses_expiring,
)
from services_api.dashboard.v2.library_quotas import (
    _DEFAULT_QUOTAS,
    check_quota_before_upload,
    recalculate_quotas,
)




@pytest.mark.asyncio
async def test_license_catalogue_returns_seeded_row(mock_pool):
    mock_pool.fetchrow.return_value = {
        "config_value": json.dumps([
            {"id": "cc0", "label": "CC0", "commercial": True, "attribution": False},
        ])
    }
    resp = await license_catalogue(_=None)
    assert resp["source"] == "system_config"
    assert resp["data"][0]["id"] == "cc0"


@pytest.mark.asyncio
async def test_license_catalogue_falls_back_when_row_missing(mock_pool):
    mock_pool.fetchrow.return_value = None
    resp = await license_catalogue(_=None)
    assert resp["source"] == "fallback"
    assert resp["data"] == _catalogue_fallback()


@pytest.mark.asyncio
async def test_license_catalogue_falls_back_on_invalid_json(mock_pool):
    mock_pool.fetchrow.return_value = {"config_value": "{not json"}
    resp = await license_catalogue(_=None)
    assert resp["source"] == "fallback"


@pytest.mark.asyncio
async def test_licenses_expiring_uses_within_days_window(mock_pool):
    mock_pool.fetch.return_value = []
    await licenses_expiring(within_days=30, scope="workspace", scope_id=None, limit=200, _=None)
    sql, *params = mock_pool.fetch.await_args.args
    assert "expires_at IS NOT NULL" in sql
    assert "ORDER BY expires_at ASC" in sql
    assert 30 in params


@pytest.mark.asyncio
async def test_licenses_audit_groups_by_license(mock_pool):
    mock_pool.fetch.return_value = []
    await licenses_audit(scope="workspace", scope_id=None, _=None)
    sql = mock_pool.fetch.await_args.args[0]
    assert "GROUP BY COALESCE(NULLIF(license, '')" in sql
    assert "expired_count" in sql
    assert "expiring_30d" in sql




@pytest.mark.asyncio
async def test_quota_check_treats_missing_row_as_unlimited(mock_pool):
    mock_pool.fetchrow.return_value = None
    out = await check_quota_before_upload("workspace", "WS_1", incoming_bytes=10_000)
    assert out["ok"] is True
    assert out["remaining_bytes"] == -1


@pytest.mark.asyncio
async def test_quota_check_treats_zero_quota_as_unlimited(mock_pool):
    mock_pool.fetchrow.return_value = {"quota_bytes": 0, "used_bytes": 0}
    out = await check_quota_before_upload("system", "", incoming_bytes=10 ** 9)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_quota_check_rejects_when_over_quota(mock_pool):
    mock_pool.fetchrow.return_value = {"quota_bytes": 1_000, "used_bytes": 900}
    out = await check_quota_before_upload("workspace", "WS_1", incoming_bytes=200)
    assert out["ok"] is False
    assert out["remaining_bytes"] == 100


@pytest.mark.asyncio
async def test_quota_check_allows_when_at_exactly_quota(mock_pool):
    mock_pool.fetchrow.return_value = {"quota_bytes": 1_000, "used_bytes": 900}
    out = await check_quota_before_upload("workspace", "WS_1", incoming_bytes=100)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_recalculate_upserts_one_row_per_scope(mock_pool):
    mock_pool.fetchrow.return_value = None
    mock_pool.fetch.return_value = [
        {"scope": "workspace", "scope_id": "WS_1", "used_bytes": 12345},
        {"scope": "channel", "scope_id": "CH_1", "used_bytes": 678},
    ]
    touched = await recalculate_quotas()
    assert touched == 2
    upsert_calls = [c for c in mock_pool.execute.await_args_list
                    if "INSERT INTO storage_quotas" in c.args[0]]
    assert len(upsert_calls) == 2


def test_default_quotas_match_ticket_spec():
    """Sanity: the in-process fallback matches the migration seeds (100/25/10/5 GB)."""
    assert _DEFAULT_QUOTAS["workspace_bytes"] == 100 * 1024 ** 3
    assert _DEFAULT_QUOTAS["brand_bytes"] == 25 * 1024 ** 3
    assert _DEFAULT_QUOTAS["channel_bytes"] == 10 * 1024 ** 3
    assert _DEFAULT_QUOTAS["project_bytes"] == 5 * 1024 ** 3
