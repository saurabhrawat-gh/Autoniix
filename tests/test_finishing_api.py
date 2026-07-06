"""Tests for the channel finishing settings API (AE-296).

Covers: get default config, partial update, invalid preset (422), out-of-range
loudness / true-peak (422), preset listing, and role enforcement (viewer 403).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services_api.dashboard.v2.finishing import (
    FinishingConfigUpdate,
    get_finishing_config,
    list_finishing_presets,
    update_finishing_config,
)
from tests.conftest import FakePool, FakeRecord

_MOD = "services_api.dashboard.v2.finishing"


def _principal(role: str = "owner"):
    from services_api.dashboard.v2._deps import Principal
    return Principal(user_id=1, email="t@t.com", role=role, source="v2_jwt", workspace_id=1)


def _default_row():
    return FakeRecord(
        channel_id="CH_1",
        require_resolve_finish=False,
        color_grade_preset="cinematic",
        audio_denoise=True,
        audio_eq=True,
        audio_compress=True,
        audio_music_duck=True,
        audio_loudness_lufs=-14.0,
        audio_true_peak_dbtps=-1.5,
        output_prores_archive=False,
        updated_at=datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc),
    )


def _pool_with_config():
    pool = FakePool()
    pool.fetchval = AsyncMock(return_value=1)
    pool.fetchrow = AsyncMock(return_value=_default_row())
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


def _patch_pool(pool):
    return patch(f"{_MOD}.get_pool", new_callable=AsyncMock, return_value=pool)



class TestValidation:
    def test_invalid_preset_rejected(self):
        with pytest.raises(ValidationError) as exc:
            FinishingConfigUpdate(color_grade_preset="bogus")
        assert "unrecognised preset" in str(exc.value)

    def test_valid_preset_accepted(self):
        m = FinishingConfigUpdate(color_grade_preset="neon_dark")
        assert m.color_grade_preset == "neon_dark"

    def test_loudness_too_loud_rejected(self):
        with pytest.raises(ValidationError):
            FinishingConfigUpdate(audio_loudness_lufs=-5.0)

    def test_loudness_too_quiet_rejected(self):
        with pytest.raises(ValidationError):
            FinishingConfigUpdate(audio_loudness_lufs=-30.0)

    def test_loudness_in_range_ok(self):
        assert FinishingConfigUpdate(audio_loudness_lufs=-16.0).audio_loudness_lufs == -16.0

    def test_true_peak_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            FinishingConfigUpdate(audio_true_peak_dbtps=-10.0)

    def test_true_peak_in_range_ok(self):
        assert FinishingConfigUpdate(audio_true_peak_dbtps=-2.0).audio_true_peak_dbtps == -2.0



@pytest.mark.asyncio
class TestGetConfig:
    async def test_returns_default_config(self):
        pool = _pool_with_config()
        with _patch_pool(pool):
            out = await get_finishing_config("CH_1", _=_principal("viewer"))
        assert out["color_grade_preset"] == "cinematic"
        assert out["audio_loudness_lufs"] == -14.0
        assert isinstance(out["updated_at"], str)

    async def test_unknown_channel_404(self):
        pool = FakePool()
        pool.fetchval = AsyncMock(return_value=None)
        with _patch_pool(pool):
            with pytest.raises(HTTPException) as exc:
                await get_finishing_config("nope", _=_principal())
        assert exc.value.status_code == 404



@pytest.mark.asyncio
class TestUpdateConfig:
    async def test_update_applies_and_returns(self):
        pool = _pool_with_config()
        body = FinishingConfigUpdate(color_grade_preset="warm_gold", output_prores_archive=True)
        with _patch_pool(pool), patch(f"{_MOD}.audit", new_callable=AsyncMock) as aud:
            out = await update_finishing_config(
                "CH_1", body, request=AsyncMock(), actor=_principal("owner"))
        assert pool.execute.await_count >= 1
        aud.assert_awaited()
        assert "color_grade_preset" in out

    async def test_no_fields_is_noop_but_returns_config(self):
        pool = _pool_with_config()
        body = FinishingConfigUpdate()
        with _patch_pool(pool), patch(f"{_MOD}.audit", new_callable=AsyncMock):
            out = await update_finishing_config(
                "CH_1", body, request=AsyncMock(), actor=_principal("owner"))
        assert out["channel_id"] == "CH_1"

    async def test_unknown_channel_404(self):
        pool = FakePool()
        pool.fetchval = AsyncMock(return_value=None)
        body = FinishingConfigUpdate(color_grade_preset="vintage")
        with _patch_pool(pool):
            with pytest.raises(HTTPException) as exc:
                await update_finishing_config(
                    "nope", body, request=AsyncMock(), actor=_principal("owner"))
        assert exc.value.status_code == 404



@pytest.mark.asyncio
class TestRoleEnforcement:
    async def test_viewer_blocked_from_update(self):
        from services_api.dashboard.v2._deps import require_role

        checker = require_role("owner", "member")
        with pytest.raises(HTTPException) as exc:
            await checker(p=_principal("viewer"))
        assert exc.value.status_code == 403

    async def test_member_allowed(self):
        from services_api.dashboard.v2._deps import require_role

        checker = require_role("owner", "member")
        result = await checker(p=_principal("member"))
        assert result.role == "member"



@pytest.mark.asyncio
async def test_list_presets_returns_seven():
    out = await list_finishing_presets()
    assert len(out["presets"]) == 7
    keys = {p["key"] for p in out["presets"]}
    assert "cinematic" in keys and "neon_dark" in keys
