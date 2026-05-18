"""Unit tests for Phase 4 provider changes.

Covers:
- _require_cred_actor: owner always allowed
- _require_cred_actor: admin blocked without feature flag
- _require_cred_actor: admin allowed when feature flag ON
- _require_cred_actor: viewer always blocked
- create_credential: channel_id + content_mode + scope_priority stored
- rotate_credential: blocked when feature flag OFF / allowed when ON
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_PROV_MODULE = "src.services.dashboard.v2.providers"


def _make_principal(role: str = "owner", workspace_id: int = 1, user_id: int = 1):
    from src.services.dashboard.v2._deps import Principal
    return Principal(user_id=user_id, email="test@test.com", role=role,
                     source="v2_jwt", workspace_id=workspace_id)


def _pool_ctx(pool):
    return patch(f"{_PROV_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


# ---------------------------------------------------------------------------
# _require_cred_actor
# ---------------------------------------------------------------------------

class TestRequireCredActor:
    @pytest.mark.asyncio
    async def test_owner_always_allowed(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="owner")
        result = await _require_cred_actor(p=p)
        assert result.role == "owner"

    @pytest.mark.asyncio
    async def test_admin_blocked_without_flag(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="admin")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await _require_cred_actor(p=p)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allowed_with_flag(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="admin")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True):
            result = await _require_cred_actor(p=p)
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_viewer_always_blocked(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="viewer")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await _require_cred_actor(p=p)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_producer_always_blocked(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="producer")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await _require_cred_actor(p=p)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Credential scope_priority auto-computation
# ---------------------------------------------------------------------------

class TestCredentialScopes:
    async def _run_create(self, body, pool):
        from src.services.dashboard.v2.providers import create_credential
        actor = _make_principal(role="owner")
        req = MagicMock()
        with _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.put_secret_at", return_value="env"), \
             patch(f"{_PROV_MODULE}.publish_invalidate", new_callable=AsyncMock), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock), \
             patch("src.providers.registry.ProviderRegistry._registries",
                   {"llm": {"openai": MagicMock()}}):
            return await create_credential(body=body, request=req, actor=actor)

    @pytest.mark.asyncio
    async def test_workspace_scope_priority_zero(self):
        """No channel_id / content_mode → scope_priority=0."""
        from src.services.dashboard.v2.providers import CredentialIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(name="llm")  # category check
        pool.fetchval.return_value = 1  # returned cred id

        body = CredentialIn(category="llm", provider_name="openai",
                            label="main", secret_value="sk-test")
        result = await self._run_create(body, pool)

        assert result["status"] == "ok"
        # scope_priority=0 is the 9th arg in the INSERT VALUES ($1..$10)
        args = pool.fetchval.call_args[0]
        assert 0 in args  # scope_priority

    @pytest.mark.asyncio
    async def test_channel_scope_priority_ten(self):
        """channel_id only → scope_priority=10."""
        from src.services.dashboard.v2.providers import CredentialIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(name="llm")
        pool.fetchval.return_value = 2

        body = CredentialIn(category="llm", provider_name="openai",
                            label="ch-only", secret_value="sk-test",
                            channel_id="UCtest123")
        result = await self._run_create(body, pool)

        assert result["status"] == "ok"
        args = pool.fetchval.call_args[0]
        assert 10 in args

    @pytest.mark.asyncio
    async def test_channel_plus_mode_priority_twenty(self):
        """channel_id + content_mode → scope_priority=20."""
        from src.services.dashboard.v2.providers import CredentialIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(name="llm")
        pool.fetchval.return_value = 3

        body = CredentialIn(category="llm", provider_name="openai",
                            label="ch-mode", secret_value="sk-test",
                            channel_id="UCtest123", content_mode="short")
        result = await self._run_create(body, pool)

        assert result["status"] == "ok"
        args = pool.fetchval.call_args[0]
        assert 20 in args


# ---------------------------------------------------------------------------
# Rotate credential feature flag
# ---------------------------------------------------------------------------

class TestRotateCredential:
    @pytest.mark.asyncio
    async def test_rotate_blocked_when_flag_off(self):
        from src.services.dashboard.v2.providers import rotate_credential, RotateIn

        pool = FakePool()
        actor = _make_principal(role="owner")
        body = RotateIn(secret_value="sk-new")
        req = MagicMock()

        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=False), \
             _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc_info:
                await rotate_credential(credential_id=1, body=body, request=req, actor=actor)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rotate_allowed_when_flag_on(self):
        from src.services.dashboard.v2.providers import rotate_credential, RotateIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1, category="llm", provider_name="openai", label="main",
            vault_path="providers/llm/openai/main",
        )
        pool.execute = AsyncMock(return_value="UPDATE 1")

        actor = _make_principal(role="owner")
        body = RotateIn(secret_value="sk-new")
        req = MagicMock()

        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True), \
             _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.put_secret_at", return_value="env"), \
             patch(f"{_PROV_MODULE}.get_secret_at", return_value="sk-old"), \
             patch(f"{_PROV_MODULE}.publish_invalidate", new_callable=AsyncMock), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock):
            result = await rotate_credential(credential_id=1, body=body, request=req, actor=actor)
        assert result["status"] == "ok"
