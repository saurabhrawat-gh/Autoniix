"""Unit tests for Phase 4 provider changes.

Covers:
- _require_cred_actor: owner always allowed
- _require_cred_actor: admin blocked without feature flag
- _require_cred_actor: admin allowed when feature flag ON
- _require_cred_actor: viewer always blocked
- create_credential: channel_id + content_mode + scope_priority stored
- create_credential: workspace_id stored from actor (AE-300)
- list_credentials: workspace_id filter applied for non-superadmin (AE-300)
- delete_credential: cross-workspace delete blocked with 403 (AE-300)
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
    async def test_member_blocked_without_flag(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="member")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await _require_cred_actor(p=p)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_member_allowed_with_flag(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="member")
        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True):
            result = await _require_cred_actor(p=p)
        assert result.role == "member"

    @pytest.mark.asyncio
    async def test_viewer_always_blocked(self):
        from src.services.dashboard.v2.providers import _require_cred_actor

        p = _make_principal(role="viewer")
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
            extra_config={},
        )
        pool.execute = AsyncMock(return_value="UPDATE 1")

        actor = _make_principal(role="owner")
        body = RotateIn(secret_value="sk-new")
        req = MagicMock()

        # Mock the safe-swap health check: provider class returns health_ok=True
        mock_inst = MagicMock()
        mock_inst.health_check = AsyncMock(return_value=True)
        mock_inst.api_key = ""
        mock_cls = MagicMock(return_value=mock_inst)

        with patch(f"{_PROV_MODULE}.flag_enabled", new_callable=AsyncMock, return_value=True), \
             _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.put_secret_at", return_value="env"), \
             patch(f"{_PROV_MODULE}.get_secret_at", return_value="sk-staged"), \
             patch("src.providers.registry.ProviderRegistry._registries",
                   {"llm": {"openai": mock_cls}}), \
             patch(f"{_PROV_MODULE}.publish_invalidate", new_callable=AsyncMock), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock):
            result = await rotate_credential(credential_id=1, body=body, request=req, actor=actor)
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# AE-300: Workspace scoping (no cross-workspace data leak)
# ---------------------------------------------------------------------------

class TestWorkspaceScoping:
    @pytest.mark.asyncio
    async def test_create_credential_stores_workspace_id(self):
        """workspace_id from actor is persisted in the INSERT."""
        from src.services.dashboard.v2.providers import CredentialIn, create_credential

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(name="llm")
        pool.fetchval.return_value = 42

        actor = _make_principal(role="owner", workspace_id=7)
        body = CredentialIn(category="llm", provider_name="openai",
                            label="ws-test", secret_value="sk-x")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.put_secret_at", return_value="env"), \
             patch(f"{_PROV_MODULE}.publish_invalidate", new_callable=AsyncMock), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock), \
             patch("src.providers.registry.ProviderRegistry._registries",
                   {"llm": {"openai": MagicMock()}}):
            result = await create_credential(body=body, request=req, actor=actor)

        assert result["status"] == "ok"
        insert_args = pool.fetchval.call_args[0]
        assert 7 in insert_args, "workspace_id=7 must be in INSERT args"

    @pytest.mark.asyncio
    async def test_delete_cross_workspace_blocked(self):
        """DELETE /credentials/{id} returns 403 when credential belongs to another workspace."""
        from src.services.dashboard.v2.providers import delete_credential

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(category="llm", workspace_id=99)

        actor = _make_principal(role="owner", workspace_id=1)
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await delete_credential(credential_id=5, request=req, actor=actor)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_same_workspace_allowed(self):
        """DELETE /credentials/{id} succeeds when credential belongs to same workspace."""
        from src.services.dashboard.v2.providers import delete_credential

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(category="llm", workspace_id=1)
        pool.execute = AsyncMock(return_value="DELETE 1")

        actor = _make_principal(role="owner", workspace_id=1)
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock), \
             patch(f"{_PROV_MODULE}.publish_invalidate", new_callable=AsyncMock):
            result = await delete_credential(credential_id=5, request=req, actor=actor)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_list_credentials_adds_workspace_filter_for_regular_user(self):
        """GET /credentials applies workspace_id filter for non-superadmin."""
        from src.services.dashboard.v2.providers import list_credentials

        pool = FakePool()
        pool.fetch.return_value = []

        actor = _make_principal(role="owner", workspace_id=3)

        with _pool_ctx(pool):
            await list_credentials(actor=actor)

        call_args = pool.fetch.call_args
        sql = call_args[0][0] if call_args[0] else str(call_args)
        positional_args = call_args[0][1:] if call_args[0] else call_args[1].get("args", [])
        assert 3 in positional_args, "workspace_id=3 must be bound in query args"


# ---------------------------------------------------------------------------
# AE-318: delete_kind — FK-safe purge of marketplace catalog entries
# ---------------------------------------------------------------------------

class TestDeleteKind:
    @pytest.mark.asyncio
    async def test_delete_kind_purges_all_catalog_entries(self):
        """_purge_category must DELETE FROM provider_marketplace_catalog WHERE category=$1
        without filtering on is_user_defined, otherwise the FK constraint
        (marketplace_catalog.category → provider_categories.name, no CASCADE)
        raises an error when built-in catalog rows remain → HTTP 500.
        Regression test for AE-318."""
        from src.services.dashboard.v2.providers import delete_kind
        from tests.conftest import FakePool, FakeRecord

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(kind="storage")
        pool.fetch.return_value = [FakeRecord(name="storage")]

        actor = _make_principal(role="owner")
        req = MagicMock()

        with _pool_ctx(pool), \
             patch(f"{_PROV_MODULE}.audit", new_callable=AsyncMock):
            result = await delete_kind(kind="storage", request=req, actor=actor)

        assert result["status"] == "ok"
        assert result["categories_removed"] == ["storage"]

        executed_sqls = [call[0][0] for call in pool.conn.execute.call_args_list]
        catalog_deletes = [s for s in executed_sqls if "provider_marketplace_catalog" in s]
        assert catalog_deletes, "expected at least one DELETE on provider_marketplace_catalog"
        for sql in catalog_deletes:
            assert "is_user_defined" not in sql, (
                "FK-safe purge must not filter on is_user_defined — "
                "built-in catalog rows would remain and violate the FK constraint"
            )
