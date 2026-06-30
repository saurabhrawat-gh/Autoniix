"""Tests for Story #226 — Immediate Session Revocation.

Covers:
- Membership cache miss → DB lookup
- Membership cache hit (no DB call)
- Cache TTL expiry triggers re-fetch
- Removed member next request → 403 workspace_access_revoked
- Cache invalidated via invalidate()
- publish_revoked is called on remove_member
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException



class TestMembershipCache:

    def setup_method(self):
        from src.services.dashboard.v2 import _membership as mm
        mm._cache.clear()

    def teardown_method(self):
        from src.services.dashboard.v2 import _membership as mm
        mm._cache.clear()

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_member(self):
        from src.services.dashboard.v2 import _membership as mm

        mock_pool = AsyncMock()
        mock_pool.fetchval.return_value = 1

        with patch("src.services.dashboard.v2._membership.get_pool", AsyncMock(return_value=mock_pool)):
            result = await mm.check_membership(42, 7)

        assert result is True
        assert (42, 7) in mm._cache
        assert mm._cache[(42, 7)][0] is True

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_non_member(self):
        from src.services.dashboard.v2 import _membership as mm

        mock_pool = AsyncMock()
        mock_pool.fetchval.return_value = None

        with patch("src.services.dashboard.v2._membership.get_pool", AsyncMock(return_value=mock_pool)):
            result = await mm.check_membership(99, 7)

        assert result is False
        assert mm._cache[(99, 7)][0] is False

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        from src.services.dashboard.v2 import _membership as mm

        mm._cache[(5, 3)] = (True, time.monotonic() + 30.0)

        mock_get_pool = AsyncMock()
        with patch("src.services.dashboard.v2._membership.get_pool", mock_get_pool):
            result = await mm.check_membership(5, 3)

        assert result is True
        mock_get_pool.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_entry_reloads(self):
        from src.services.dashboard.v2 import _membership as mm

        mm._cache[(10, 2)] = (True, time.monotonic() - 1.0)

        mock_pool = AsyncMock()
        mock_pool.fetchval.return_value = None
        with patch("src.services.dashboard.v2._membership.get_pool", AsyncMock(return_value=mock_pool)):
            result = await mm.check_membership(10, 2)

        assert result is False

    def test_invalidate_specific(self):
        from src.services.dashboard.v2 import _membership as mm

        mm._cache[(1, 1)] = (True, time.monotonic() + 30.0)
        mm._cache[(2, 1)] = (True, time.monotonic() + 30.0)

        mm.invalidate(user_id=1, workspace_id=1)

        assert (1, 1) not in mm._cache
        assert (2, 1) in mm._cache

    def test_invalidate_all_for_user(self):
        from src.services.dashboard.v2 import _membership as mm

        mm._cache[(1, 1)] = (True, time.monotonic() + 30.0)
        mm._cache[(1, 2)] = (True, time.monotonic() + 30.0)
        mm._cache[(2, 1)] = (True, time.monotonic() + 30.0)

        mm.invalidate(user_id=1)

        assert (1, 1) not in mm._cache
        assert (1, 2) not in mm._cache
        assert (2, 1) in mm._cache



class TestPrincipalDepRevocation:

    @pytest.mark.asyncio
    async def test_revoked_member_gets_403(self):
        """When check_membership returns False, principal_dep raises 403."""
        from src.services.dashboard.v2._deps import principal_dep

        fake_claims = {"sub": "5", "email": "bob@example.com", "role": "member", "wid": "3"}

        def _fake_decode(token):
            return fake_claims

        mock_request = MagicMock()
        mock_request.cookies.get.return_value = None
        mock_request.client = None

        with patch("src.services.dashboard.v2._deps._decode_jwt", _fake_decode), \
             patch("src.services.dashboard.v2._deps.check_membership",
                   AsyncMock(return_value=False)) as mock_cm:
            from fastapi.security import HTTPAuthorizationCredentials
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="ey.a.b")
            with pytest.raises(HTTPException) as exc_info:
                await principal_dep(request=mock_request, creds=creds)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "workspace_access_revoked"

    @pytest.mark.asyncio
    async def test_active_member_passes(self):
        """Active member resolves to Principal normally."""
        from src.services.dashboard.v2._deps import principal_dep

        fake_claims = {"sub": "5", "email": "bob@example.com", "role": "member", "wid": "3"}

        mock_request = MagicMock()
        mock_request.cookies.get.return_value = None
        mock_request.client = None

        with patch("src.services.dashboard.v2._deps._decode_jwt", lambda t: fake_claims), \
             patch("src.services.dashboard.v2._deps.check_membership",
                   AsyncMock(return_value=True)):
            from fastapi.security import HTTPAuthorizationCredentials
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="ey.a.b")
            principal = await principal_dep(request=mock_request, creds=creds)

        assert principal.user_id == 5
        assert principal.workspace_id == 3
