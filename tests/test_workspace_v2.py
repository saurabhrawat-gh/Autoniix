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

_WS_MODULE = "services_api.dashboard.v2.workspace"


def _make_principal(role: str = "owner", workspace_id: int = 1, user_id: int = 42):
    from services_api.dashboard.v2._deps import Principal
    return Principal(user_id=user_id, email="test@test.com", role=role,
                     source="v2_jwt", workspace_id=workspace_id)


def _pool_ctx(pool):
    """Return a patch for the module-local get_pool in workspace.py."""
    return patch(f"{_WS_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)



class TestPlanLimits:
    @pytest.mark.asyncio
    async def test_plan_limit_blocks_invite_when_full(self):
        """Starter plan (limit=3) blocks invite when 3 seats already taken."""
        from services_api.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="starter")]
        pool.conn.fetchval.side_effect = [3, 0]

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
        from services_api.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="starter"),
            None,
        ]
        pool.conn.fetchval.side_effect = [2, 0, None, None, 99]

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
        from services_api.dashboard.v2.workspace import create_invite, InviteIn
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="enterprise"),
            None,
        ]
        pool.conn.fetchval.side_effect = [None, None, 99]

        actor = _make_principal(role="owner")
        body = InviteIn(email="anyone@test.com", role="member")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await create_invite(body=body, request=req, actor=actor)
        assert result["status"] == "ok"



class TestLastOwnerProtection:
    @pytest.mark.asyncio
    async def test_cannot_demote_last_owner(self):
        """Demoting the only owner should raise HTTP 400."""
        from services_api.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval.side_effect = ["owner", 1]

        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="member")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await set_member_role(user_id=99, body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 400
        assert "last owner" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_can_demote_owner_when_multiple_owners_exist(self):
        """Demoting one of two owners should succeed."""
        from services_api.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval.side_effect = ["owner", 2]
        pool.execute = AsyncMock(return_value="UPDATE 1")

        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="member")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await set_member_role(user_id=99, body=body, request=req, actor=actor)
        assert result["status"] == "ok"



class TestRoleValidation:
    @pytest.mark.asyncio
    async def test_invalid_role_rejected_on_invite(self):
        """Legacy roles like 'reviewer' must be rejected."""
        from services_api.dashboard.v2.workspace import create_invite, InviteIn
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
        from services_api.dashboard.v2.workspace import set_member_role, MemberRolePatch
        from tests.conftest import FakePool

        pool = FakePool()
        actor = _make_principal(role="owner")
        body = MemberRolePatch(role="analyst")
        req = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await set_member_role(user_id=1, body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 400



class TestWorkspaceIntegrations:
    @pytest.mark.asyncio
    async def test_get_integrations_returns_null_when_none_configured(self):
        from services_api.dashboard.v2.workspace import get_integrations
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchrow.return_value = None
        actor = _make_principal(role="owner")

        with _pool_ctx(pool):
            result = await get_integrations(actor=actor)
        assert result["data"]["slack_webhook_url"] is None

    @pytest.mark.asyncio
    async def test_get_integrations_returns_url(self):
        from services_api.dashboard.v2.workspace import get_integrations
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
        from services_api.dashboard.v2.workspace import update_integrations, IntegrationPatch
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



class TestEntitySettingsTenantIsolation:
    """Regression: ``GET /workspace/settings`` and ``PUT /workspace/settings``
    must reject any ``scope_id`` whose owning workspace does not match the
    caller's workspace.  Bug AE-276."""

    @pytest.mark.asyncio
    async def test_get_settings_rejects_foreign_workspace_scope_id(self):
        """READ leak fix: caller in workspace 1 cannot read workspace 2's settings."""
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        actor = _make_principal(role="owner", workspace_id=1)

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_settings(scope="workspace", scope_id="2", p=actor)
        assert exc_info.value.status_code == 403
        assert "cross-workspace" in exc_info.value.detail.lower()
        pool.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_put_settings_rejects_foreign_workspace_scope_id(self):
        """WRITE leak fix (more severe): caller in workspace 1 cannot upsert into
        workspace 2's entity_settings — verifies the audit + INSERT never runs."""
        from services_api.dashboard.v2.workspace import upsert_setting, EntitySettingUpsert
        from tests.conftest import FakePool

        pool = FakePool()
        body = EntitySettingUpsert(
            scope="workspace", scope_id="999", key="qa_canary",
            value={"tampered": True}, locked=False,
        )
        actor = _make_principal(role="owner", workspace_id=1)
        req = MagicMock()

        with _pool_ctx(pool), patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock) as audit_mock:
            with pytest.raises(HTTPException) as exc_info:
                await upsert_setting(body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 403
        pool.execute.assert_not_called()
        audit_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_settings_allows_own_workspace_scope_id(self):
        """No regression: same-workspace scope_id continues to work."""
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetch = AsyncMock(return_value=[
            FakeRecord(key="onboarding", value={"completed": True}, locked=False),
        ])
        actor = _make_principal(role="owner", workspace_id=42)

        with _pool_ctx(pool):
            result = await get_settings(scope="workspace", scope_id="42", p=actor)
        assert len(result["data"]) == 1
        assert result["data"][0]["key"] == "onboarding"

    @pytest.mark.asyncio
    async def test_put_settings_allows_own_workspace_scope_id(self):
        """No regression: same-workspace upsert continues to work."""
        from services_api.dashboard.v2.workspace import upsert_setting, EntitySettingUpsert
        from tests.conftest import FakePool

        pool = FakePool()
        pool.execute = AsyncMock(return_value="INSERT 0 1")
        body = EntitySettingUpsert(
            scope="workspace", scope_id="42", key="onboarding",
            value={"completed": True}, locked=False,
        )
        actor = _make_principal(role="owner", workspace_id=42)
        req = MagicMock()

        with _pool_ctx(pool), patch(f"{_WS_MODULE}.audit", new_callable=AsyncMock):
            result = await upsert_setting(body=body, request=req, actor=actor)
        assert result["status"] == "ok"
        pool.execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scope,owner_workspace_id",
        [
            ("brand", 2),
            ("series", 2),
            ("campaign", 2),
            ("project", 2),
            ("channel", 2),
        ],
        ids=["brand", "series", "campaign", "project", "channel"],
    )
    async def test_get_settings_rejects_foreign_owner_for_all_tenant_scopes(
        self, scope: str, owner_workspace_id: int,
    ):
        """For every non-workspace tenant scope, foreign-owned entity → 403.

        The handler resolves the entity's owning workspace_id via JOIN and
        compares to the caller's workspace.  Caller is in WS 1; entity is
        owned by WS 2; expected 403.
        """
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval = AsyncMock(return_value=owner_workspace_id)
        actor = _make_principal(role="owner", workspace_id=1)
        scope_id = "UCfakeChannelId" if scope == "channel" else "777"

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_settings(scope=scope, scope_id=scope_id, p=actor)
        assert exc_info.value.status_code == 403
        pool.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_settings_returns_404_for_nonexistent_entity(self):
        """If the entity doesn't exist at all, 404 (not 403 — distinct contract)."""
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetchval = AsyncMock(return_value=None)
        actor = _make_principal(role="owner", workspace_id=1)

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_settings(scope="brand", scope_id="9999", p=actor)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_settings_invalid_scope_id_for_int_scope_returns_400(self):
        """Non-numeric scope_id for an int-keyed scope returns 400, not 500."""
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        actor = _make_principal(role="owner", workspace_id=1)

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_settings(scope="brand", scope_id="not-an-int", p=actor)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_system_scope_passes_through_without_tenant_check(self):
        """``scope='system'`` is platform-wide, not per-tenant — the ownership
        gate must skip it.  Caller permission is the only authorization layer."""
        from services_api.dashboard.v2.workspace import get_settings
        from tests.conftest import FakePool

        pool = FakePool()
        pool.fetch = AsyncMock(return_value=[])
        actor = _make_principal(role="owner", workspace_id=1)

        with _pool_ctx(pool):
            result = await get_settings(scope="system", scope_id="any", p=actor)
        assert result == {"data": []}
        pool.fetchval.assert_not_called()
