"""Unit tests for Phase 3 workspace changes.

Covers:
- Plan limit enforcement on create_invite (HTTP 402)
- Last-owner demotion protection (HTTP 400)
- Workspace integrations GET / PUT
- Role validation (5-role model)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakeRecord

_WS_MODULE = "src.services.dashboard.v2.workspace"


def _make_principal(role: str = "owner", workspace_id: int = 1, user_id: int = 42):
    from src.services.dashboard.v2._deps import Principal
    return Principal(user_id=user_id, email="test@test.com", role=role,
                     source="v2_jwt", workspace_id=workspace_id)


def _pool_ctx(pool):
    """Return a patch for the module-local get_pool in workspace.py."""
    return patch(f"{_WS_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


# ---------------------------------------------------------------------------
# Plan limit tests
# ---------------------------------------------------------------------------

class TestPlanLimits:
    @pytest.mark.asyncio
    async def test_plan_limit_blocks_invite_when_full(self):
        """Starter plan (limit=3) blocks invite when 3 seats already taken."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="starter")]
        pool.fetchval.side_effect = [3, 0]  # member_count=3, pending=0

        actor = _make_principal(role="owner")
        body = InviteIn(email="newuser@test.com", role="viewer")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await create_invite(body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 402
        assert "plan limit" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_plan_limit_allows_invite_within_limit(self):
        """Starter plan with 2 members allows one more invite."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="starter"),  # plan lookup
            None,                        # no existing member
            None,                        # no slack integration
        ]
        # member_count=2, pending=0, existing=None (no dup), inv_id=99
        pool.fetchval.side_effect = [2, 0, None, 99]
        pool.execute = AsyncMock(return_value="INSERT 0 1")

        actor = _make_principal(role="owner")
        body = InviteIn(email="newuser@test.com", role="viewer")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await create_invite(body=body, request=req, actor=actor)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_enterprise_plan_has_no_limit(self):
        """Enterprise plan (unlimited) never blocks invites."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="enterprise"),  # plan lookup
            None,                           # no existing member
            None,                           # no slack integration
        ]
        # No limit check → only: existing=None, inv_id=99
        pool.fetchval.side_effect = [None, 99]
        pool.execute = AsyncMock(return_value="INSERT 0 1")

        actor = _make_principal(role="owner")
        body = InviteIn(email="anyone@test.com", role="editor")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await create_invite(body=body, request=req, actor=actor)
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Last-owner protection tests
# ---------------------------------------------------------------------------

class TestLastOwnerProtection:
    @pytest.mark.asyncio
    async def test_cannot_demote_last_owner(self):
        """Demoting the only owner should raise HTTP 400."""
        from src.services.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval.side_effect = ["owner", 1]  # current_role, owner_count

        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="admin")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await set_member_role(user_id=99, body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 400
        assert "last owner" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_can_demote_owner_when_multiple_owners_exist(self):
        """Demoting one of two owners should succeed."""
        from src.services.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval.side_effect = ["owner", 2]  # current_role, owner_count=2 → safe
        pool.execute = AsyncMock(return_value="UPDATE 1")

        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="admin")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await set_member_role(user_id=99, body=body, request=req, actor=actor)
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Role validation tests
# ---------------------------------------------------------------------------

class TestRoleValidation:
    @pytest.mark.asyncio
    async def test_invalid_role_rejected_on_invite(self):
        """Legacy roles like 'reviewer' must be rejected."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        actor = _make_principal(role="owner")
        body = InviteIn(email="x@test.com", role="reviewer")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await create_invite(body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_role_rejected_on_role_update(self):
        """Legacy role 'analyst' must be rejected on role update."""
        from src.services.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="analyst")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await set_member_role(user_id=1, body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Workspace integrations tests
# ---------------------------------------------------------------------------

class TestWorkspaceIntegrations:
    @pytest.mark.asyncio
    async def test_get_integrations_returns_null_when_none_configured(self):
        from src.services.dashboard.v2.workspace import get_integrations
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.return_value = None
        actor = _make_principal(role="owner")

        with _pool_ctx(pool):
            result = await get_integrations(actor=actor)
        assert result["data"]["slack_webhook_url"] is None

    @pytest.mark.asyncio
    async def test_get_integrations_returns_url(self):
        from src.services.dashboard.v2.workspace import get_integrations
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            slack_webhook_url="https://hooks.slack.com/services/TEST"
        )
        actor = _make_principal(role="owner")

        with _pool_ctx(pool):
            result = await get_integrations(actor=actor)
        assert result["data"]["slack_webhook_url"] == "https://hooks.slack.com/services/TEST"

    @pytest.mark.asyncio
    async def test_update_integrations_upserts(self):
        from src.services.dashboard.v2.workspace import update_integrations, IntegrationPatch
        from tests.conftest import FakePool

        pool = FakePool()
        pool.execute = AsyncMock(return_value="INSERT 0 1")
        actor = _make_principal(role="owner")
        body = IntegrationPatch(slack_webhook_url="https://hooks.slack.com/services/XYZ")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await update_integrations(body=body, request=req, actor=actor)
        assert result["status"] == "ok"
        pool.execute.assert_called_once()
