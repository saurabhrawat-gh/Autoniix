"""Tests for Story #218 — Named Permission System.

Covers:
- Permission granted path
- Permission denied (HTTP 403) path
- Admin-cannot-assign-owner guard
- Invalid role returns HTTP 400
- Cache hit path (warm cache, no DB round-trip)
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException



def _make_principal(role: str, workspace_id: int = 1):
    from src.services.dashboard.v2._deps import Principal
    return Principal(user_id=1, email="user@test.com", role=role,
                     workspace_id=workspace_id, source="v2_jwt")



class TestPermissionCache:
    """Unit-tests for the in-process TTL cache in _permissions.py."""

    def setup_method(self):
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    def teardown_method(self):
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self):
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = [{"permission": "workspace.view"}, {"permission": "channel.view"}]

        with patch("src.services.dashboard.v2._permissions.get_pool", return_value=AsyncMock(return_value=mock_pool)):
            pm._cache.clear()
            mock_get_pool = AsyncMock(return_value=mock_pool)
            with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
                perms = await pm.get_permissions_for_role("viewer")

        assert "workspace.view" in perms
        assert "channel.view" in perms

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["owner"] = (frozenset(["workspace.view", "workspace.billing.manage"]),
                               time.monotonic() + 30.0)

        mock_get_pool = AsyncMock()
        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            perms = await pm.get_permissions_for_role("owner")

        assert "workspace.billing.manage" in perms
        mock_get_pool.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_cache_reloads(self):
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["member"] = (frozenset(["workspace.view"]), time.monotonic() - 1.0)

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = [{"permission": "workspace.settings.edit"}]
        mock_get_pool = AsyncMock(return_value=mock_pool)
        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            perms = await pm.get_permissions_for_role("member")

        assert "workspace.settings.edit" in perms
        mock_get_pool.assert_called_once()

    def test_invalidate_single_role(self):
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["viewer"] = (frozenset(["workspace.view"]), time.monotonic() + 30.0)
        pm._cache["member"] = (frozenset(["workspace.view"]), time.monotonic() + 30.0)

        pm.invalidate("viewer")

        assert "viewer" not in pm._cache
        assert "member" in pm._cache

    def test_invalidate_all(self):
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["viewer"] = (frozenset(["workspace.view"]), time.monotonic() + 30.0)
        pm._cache["member"] = (frozenset(["workspace.view"]), time.monotonic() + 30.0)

        pm.invalidate(None)

        assert len(pm._cache) == 0



class TestRequirePermission:
    """Tests for the require_permission() dependency factory in _deps.py."""

    @pytest.mark.asyncio
    async def test_permission_granted(self):
        from src.services.dashboard.v2._deps import require_permission
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["owner"] = (frozenset(["workspace.ownership.transfer"]), time.monotonic() + 30.0)
        principal = _make_principal("owner")

        checker = require_permission("workspace.ownership.transfer")
        with patch("src.services.dashboard.v2._deps.principal_dep", return_value=principal):
            result = await checker(p=principal)
        assert result is principal

    @pytest.mark.asyncio
    async def test_permission_denied_returns_403(self):
        from src.services.dashboard.v2._deps import require_permission
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["viewer"] = (frozenset(["workspace.view", "channel.view"]), time.monotonic() + 30.0)
        principal = _make_principal("viewer")

        checker = require_permission("workspace.billing.manage")
        with pytest.raises(HTTPException) as exc_info:
            await checker(p=principal)

        assert exc_info.value.status_code == 403
        assert "workspace.billing.manage" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_403_detail_format(self):
        from src.services.dashboard.v2._deps import require_permission
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["member"] = (frozenset(["project.view"]), time.monotonic() + 30.0)
        principal = _make_principal("member")

        checker = require_permission("workspace.integrations.view")
        with pytest.raises(HTTPException) as exc_info:
            await checker(p=principal)

        assert exc_info.value.detail == "Permission denied: workspace.integrations.view"



class TestNonOwnerCannotAssignOwner:
    """The set_member_role endpoint must block non-owners from assigning owner role."""

    @pytest.mark.asyncio
    async def test_member_assign_owner_returns_403(self, mock_db_pool):
        """Member calling PUT /members/:id/role with role=owner gets HTTP 403."""
        from src.services.dashboard.v2.workspace import set_member_role
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["member"] = (frozenset(["workspace.members.role.change"]), time.monotonic() + 30.0)
        actor = _make_principal("member")

        class Body:
            role = "owner"

        with pytest.raises(HTTPException) as exc_info:
            await set_member_role(user_id=99, body=Body(), request=MagicMock(), actor=actor)

        assert exc_info.value.status_code == 403
        assert "owner" in exc_info.value.detail.lower()



class TestInvalidRoleValidation:
    """Legacy role strings (analyst, reviewer) must still return HTTP 400."""

    @pytest.mark.asyncio
    async def test_invalid_role_on_invite_returns_400(self, mock_db_pool):
        from src.services.dashboard.v2.workspace import create_invite
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["owner"] = (frozenset(["workspace.members.invite"]), time.monotonic() + 30.0)
        actor = _make_principal("owner")

        class Body:
            role = "analyst"
            email = "x@example.com"
            message = None

        with pytest.raises(HTTPException) as exc_info:
            await create_invite(body=Body(), request=MagicMock(), actor=actor)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_role_on_member_update_returns_400(self, mock_db_pool):
        from src.services.dashboard.v2.workspace import set_member_role
        from src.services.dashboard.v2 import _permissions as pm

        pm._cache["owner"] = (frozenset(["workspace.members.role.change"]), time.monotonic() + 30.0)
        actor = _make_principal("owner")

        class Body:
            role = "reviewer"

        with pytest.raises(HTTPException) as exc_info:
            await set_member_role(user_id=2, body=Body(), request=MagicMock(), actor=actor)

        assert exc_info.value.status_code == 400
