"""Unit tests for AE-290 channel hard-delete endpoint.

Covers:
- Successful delete (correct password + confirmation + no videos)
- Wrong password → 403 wrong_password
- Wrong confirmation string → 422 (pydantic validation)
- Channel has videos → 409 has_videos
- Channel in different workspace → 404 channel_not_found
- Non-existent channel → 404 channel_not_found
- Audit log emitted on success
- YouTube unlink audit emitted when provider_credentials linked
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_CH_MODULE = "services_api.dashboard.v2.channels"


def _make_principal(role: str = "owner", workspace_id: int = 1, user_id: int = 42):
    from services_api.dashboard.v2._deps import Principal

    return Principal(user_id=user_id, email="owner@test.com", role=role, source="v2_jwt", workspace_id=workspace_id)


def _pool_ctx(pool):
    return patch(f"{_CH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _channel_row(workspace_id: int = 1, channel_id: str = "ch_test"):
    return FakeRecord(
        channel_id=channel_id,
        channel_name="Test Channel",
        niche="tech",
        platform="youtube",
        status="active",
        workspace_id=workspace_id,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestChannelDelete:
    @pytest.mark.asyncio
    async def test_delete_succeeds_with_valid_inputs(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(password_hash="dummyhash"),
            _channel_row(workspace_id=1),
        ]
        pool.fetchval.side_effect = [0, None]

        actor = _make_principal()
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with (
            _pool_ctx(pool),
            patch(f"{_CH_MODULE}.audit", new_callable=AsyncMock) as mock_audit,
            patch("services_api.dashboard.v2.auth._verify_pw", return_value=True),
        ):
            result = await delete_channel(
                channel_id="ch_test",
                body=body,
                request=req,
                actor=actor,
            )

        assert result == {
            "status": "ok",
            "data": {"deleted": True, "channel_id": "ch_test"},
        }
        delete_calls = [c for c in pool.execute.await_args_list if "DELETE FROM channels" in str(c)]
        assert len(delete_calls) == 1
        mock_audit.assert_awaited_once()
        assert mock_audit.await_args.kwargs["action"] == "channel.delete"

    @pytest.mark.asyncio
    async def test_delete_emits_youtube_unlink_when_linked(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(password_hash="hash"),
            _channel_row(),
        ]
        pool.fetchval.side_effect = [0, 1]

        actor = _make_principal()
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with (
            _pool_ctx(pool),
            patch(f"{_CH_MODULE}.audit", new_callable=AsyncMock) as mock_audit,
            patch("services_api.dashboard.v2.auth._verify_pw", return_value=True),
        ):
            await delete_channel(
                channel_id="ch_test",
                body=body,
                request=req,
                actor=actor,
            )

        assert mock_audit.await_count == 2
        actions = [c.kwargs["action"] for c in mock_audit.await_args_list]
        assert "channel.delete" in actions
        assert "provider.youtube.unlink" in actions

    @pytest.mark.asyncio
    async def test_wrong_password_returns_403(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(password_hash="hash")]

        actor = _make_principal()
        body = ChannelDeleteIn(confirmation="delete", password="wrong")
        req = MagicMock()

        with _pool_ctx(pool), patch("services_api.dashboard.v2.auth._verify_pw", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await delete_channel(
                    channel_id="ch_test",
                    body=body,
                    request=req,
                    actor=actor,
                )
        assert exc.value.status_code == 403
        assert exc.value.detail == {"code": "wrong_password"}
        assert pool.fetchrow.await_count == 1

    @pytest.mark.asyncio
    async def test_wrong_confirmation_rejected_at_schema(self):
        from pydantic import ValidationError

        from services_api.dashboard.v2.channels import ChannelDeleteIn

        with pytest.raises(ValidationError):
            ChannelDeleteIn(confirmation="DELETE", password="x")
        with pytest.raises(ValidationError):
            ChannelDeleteIn(confirmation="del", password="x")
        with pytest.raises(ValidationError):
            ChannelDeleteIn(confirmation="", password="x")

    @pytest.mark.asyncio
    async def test_channel_in_other_workspace_returns_404(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(password_hash="hash"),
            _channel_row(workspace_id=99),
        ]

        actor = _make_principal(workspace_id=1)
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with _pool_ctx(pool), patch("services_api.dashboard.v2.auth._verify_pw", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await delete_channel(
                    channel_id="ch_test",
                    body=body,
                    request=req,
                    actor=actor,
                )
        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": "channel_not_found"}

    @pytest.mark.asyncio
    async def test_nonexistent_channel_returns_404(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(password_hash="hash"),
            None,
        ]

        actor = _make_principal()
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with _pool_ctx(pool), patch("services_api.dashboard.v2.auth._verify_pw", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await delete_channel(
                    channel_id="ghost",
                    body=body,
                    request=req,
                    actor=actor,
                )
        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": "channel_not_found"}

    @pytest.mark.asyncio
    async def test_channel_with_videos_returns_409(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(password_hash="hash"),
            _channel_row(),
        ]
        pool.fetchval.side_effect = [5]

        actor = _make_principal()
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with _pool_ctx(pool), patch("services_api.dashboard.v2.auth._verify_pw", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await delete_channel(
                    channel_id="ch_test",
                    body=body,
                    request=req,
                    actor=actor,
                )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "has_videos"
        assert exc.value.detail["video_count"] == 5
        delete_calls = [c for c in pool.execute.await_args_list if "DELETE FROM channels" in str(c)]
        assert len(delete_calls) == 0

    @pytest.mark.asyncio
    async def test_no_user_context_returns_403(self):
        from services_api.dashboard.v2.channels import (
            ChannelDeleteIn,
            delete_channel,
        )

        pool = FakePool()
        actor = _make_principal()
        actor.user_id = None
        body = ChannelDeleteIn(confirmation="delete", password="goodpw")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await delete_channel(
                    channel_id="ch_test",
                    body=body,
                    request=req,
                    actor=actor,
                )
        assert exc.value.status_code == 403


class TestRequireRoleEnforcement:
    """Verify the require_role("owner") dependency forbids member/viewer."""

    @pytest.mark.asyncio
    async def test_member_role_forbidden(self):
        from services_api.dashboard.v2._deps import Principal, require_role

        checker = require_role("owner")
        member = Principal(user_id=10, email="m@m.com", role="member", source="v2_jwt", workspace_id=1)
        with pytest.raises(HTTPException) as exc:
            await checker(p=member)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_role_forbidden(self):
        from services_api.dashboard.v2._deps import Principal, require_role

        checker = require_role("owner")
        viewer = Principal(user_id=11, email="v@v.com", role="viewer", source="v2_jwt", workspace_id=1)
        with pytest.raises(HTTPException) as exc:
            await checker(p=viewer)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_role_allowed(self):
        from services_api.dashboard.v2._deps import Principal, require_role

        checker = require_role("owner")
        owner = Principal(user_id=1, email="o@o.com", role="owner", source="v2_jwt", workspace_id=1)
        result = await checker(p=owner)
        assert result is owner
