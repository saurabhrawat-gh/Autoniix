"""Regression tests for AE-215 (#239) — permissions loud-fail.

Asserts ``get_permissions_for_role`` no longer silently returns an empty
``frozenset`` when the ``role_permissions`` table is missing/unreadable
or empty for a known role, and that ``/auth/me`` translates the new
:class:`PermissionMatrixUnavailable` exception into a clear HTTP 503.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ── _permissions.get_permissions_for_role error paths ─────────────────────


class TestGetPermissionsErrorPaths:
    def setup_method(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    def teardown_method(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    @pytest.mark.asyncio
    async def test_missing_table_raises_permission_matrix_unavailable(self) -> None:
        """Simulates the role_permissions table not existing (e.g. migration not applied)."""
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.side_effect = RuntimeError(
            'relation "role_permissions" does not exist'
        )
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            with pytest.raises(pm.PermissionMatrixUnavailable) as exc_info:
                await pm.get_permissions_for_role("owner")

        assert "role_permissions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_matrix_for_known_role_raises(self) -> None:
        """Owner with zero seeded perms → RBAC catalog uninitialized → raises."""
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = []  # no rows for known role
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            with pytest.raises(pm.PermissionMatrixUnavailable) as exc_info:
                await pm.get_permissions_for_role("owner")

        assert "uninitialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_empty_matrix_for_unknown_role_returns_empty(self) -> None:
        """An unknown role legitimately has no permissions — must NOT raise."""
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = []
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            perms = await pm.get_permissions_for_role("custom_role_not_in_catalog")

        assert perms == frozenset()

    @pytest.mark.asyncio
    async def test_populated_matrix_returns_frozenset(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = [
            {"permission": "workspace.view"},
            {"permission": "channel.view"},
        ]
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            perms = await pm.get_permissions_for_role("viewer")

        assert "workspace.view" in perms
        assert "channel.view" in perms

    @pytest.mark.asyncio
    async def test_verify_matrix_initialized_raises_when_uninitialized(self) -> None:
        """Startup probe loud-fails when matrix missing."""
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.side_effect = RuntimeError(
            'relation "role_permissions" does not exist'
        )
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            with pytest.raises(pm.PermissionMatrixUnavailable):
                await pm.verify_matrix_initialized()

    @pytest.mark.asyncio
    async def test_verify_matrix_initialized_succeeds_when_seeded(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm

        mock_pool = AsyncMock()
        mock_pool.fetch.return_value = [
            {"permission": f"perm.{i}"} for i in range(33)
        ]
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            await pm.verify_matrix_initialized()  # must not raise


# ── /auth/me HTTP 503 path ────────────────────────────────────────────────


class TestAuthMe503:
    def setup_method(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    def teardown_method(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm
        pm._cache.clear()

    @pytest.mark.asyncio
    async def test_me_returns_503_when_matrix_missing(self) -> None:
        from fastapi import HTTPException

        from src.services.dashboard.v2 import _permissions as pm
        from src.services.dashboard.v2._deps import Principal
        from src.services.dashboard.v2.auth import me

        principal = Principal(
            user_id=1, email="owner@test.com", role="owner",
            workspace_id=1, source="v2_jwt",
        )

        mock_pool = AsyncMock()
        # users SELECT for display_name
        mock_pool.fetchrow.return_value = None
        # role_permissions SELECT raises (missing table)
        mock_pool.fetch.side_effect = RuntimeError(
            'relation "role_permissions" does not exist'
        )
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2.auth.get_pool", mock_get_pool), \
             patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            with pytest.raises(HTTPException) as exc_info:
                await me(p=principal)

        assert exc_info.value.status_code == 503
        assert "Permission matrix not initialized" in exc_info.value.detail
        assert "make migrate" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_me_returns_200_when_matrix_populated(self) -> None:
        from src.services.dashboard.v2 import _permissions as pm
        from src.services.dashboard.v2._deps import Principal
        from src.services.dashboard.v2.auth import me

        principal = Principal(
            user_id=1, email="owner@test.com", role="owner",
            workspace_id=1, source="v2_jwt",
        )

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = None
        mock_pool.fetch.return_value = [
            {"permission": "workspace.view"},
            {"permission": "project.view"},
        ]
        mock_get_pool = AsyncMock(return_value=mock_pool)

        with patch("src.services.dashboard.v2.auth.get_pool", mock_get_pool), \
             patch("src.services.dashboard.v2._permissions.get_pool", mock_get_pool):
            result = await me(p=principal)

        assert result["data"]["role"] == "owner"
        assert "workspace.view" in result["data"]["permissions"]
        assert "project.view" in result["data"]["permissions"]
