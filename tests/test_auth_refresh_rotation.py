"""Unit tests for refresh token rotation (Story #19).

Covers test plan #32 (TC-19-*). Verifies:
- Each /refresh marks the old session row `rotated_at=NOW()` AND inserts a new row
- Replayed (already-rotated) refresh tokens return 401
- Expired / revoked / disabled-user / missing-token paths return 401
- New access_token + new refresh cookie issued on success
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "src.services.dashboard.v2.auth"


def _pool_ctx(pool):
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _build_acquire(conn_execute_mock: AsyncMock):
    """Construct an `async with pool.acquire() as conn: async with conn.transaction():`
    chain that drives `conn.execute` against the supplied mock."""
    conn = MagicMock()
    conn.execute = conn_execute_mock
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    return acquire


def _valid_session_row(user_id: int = 42, sid: int = 7):
    return FakeRecord(
        id=sid,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=15),
        revoked_at=None,
        rotated_at=None,
        email="user@example.com",
        role="owner",
        disabled=False,
    )


def _build_request(cookie_value: str | None):
    req = MagicMock()
    req.cookies = {"refresh_token": cookie_value} if cookie_value else {}
    return req


# ---------------------------------------------------------------------------
# Happy path — UC-RT-01
# ---------------------------------------------------------------------------

class TestRefreshHappyPath:
    @pytest.mark.asyncio
    async def test_refresh_marks_old_session_rotated_and_inserts_new(self):
        """TC-19-01 + TC-19-11: success path marks old row rotated and inserts new row."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        # fetchrow is called 3 times: session lookup, active_workspace lookup, ws_role lookup
        pool.fetchrow.side_effect = [
            _valid_session_row(),
            FakeRecord(active_workspace_id=1),
            FakeRecord(role="owner"),
        ]

        conn_execute = AsyncMock(return_value="UPDATE 1")
        pool.acquire = MagicMock(return_value=_build_acquire(conn_execute))

        req = _build_request("rawrefreshtoken")
        resp = MagicMock()
        resp.set_cookie = MagicMock()

        with _pool_ctx(pool):
            result = await refresh(request=req, response=resp, body=None)

        assert result["status"] == "ok"
        assert "access_token" in result and result["expires_in"] == 3600
        # Exactly 2 statements: UPDATE rotated_at, INSERT new session
        assert conn_execute.await_count == 2
        sqls = [c.args[0] for c in conn_execute.await_args_list]
        assert any("UPDATE sessions SET rotated_at=NOW()" in s for s in sqls)
        assert any("INSERT INTO sessions" in s for s in sqls)
        # Cookies set on response (access + refresh + auth_status -> 3 calls)
        assert resp.set_cookie.call_count >= 2


# ---------------------------------------------------------------------------
# Sad paths — UC-RT-02
# ---------------------------------------------------------------------------

class TestRefreshRejected:
    @pytest.mark.asyncio
    async def test_refresh_missing_cookie_and_body_returns_401(self):
        """No refresh token anywhere -> 401."""
        from src.services.dashboard.v2.auth import refresh

        req = _build_request(None)
        resp = MagicMock()

        with pytest.raises(HTTPException) as ei:
            await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_replay_of_rotated_token_returns_401(self):
        """TC-19-04 + TC-19-12: token already rotated -> 401 (replay attack)."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        rotated_row = _valid_session_row()
        rotated_row["rotated_at"] = datetime.utcnow() - timedelta(seconds=30)
        pool.fetchrow.return_value = rotated_row

        req = _build_request("rotated-token")
        resp = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_expired_token_returns_401(self):
        """TC-19-05: past expires_at -> 401."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        expired = _valid_session_row()
        expired["expires_at"] = datetime.utcnow() - timedelta(days=1)
        pool.fetchrow.return_value = expired

        req = _build_request("expired-token")
        resp = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_revoked_token_returns_401(self):
        """TC-19-06: revoked_at set (post-logout) -> 401."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        revoked = _valid_session_row()
        revoked["revoked_at"] = datetime.utcnow() - timedelta(minutes=5)
        pool.fetchrow.return_value = revoked

        req = _build_request("revoked-token")
        resp = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_unknown_token_returns_401(self):
        """TC-19-07: token not in DB (tampered/forged) -> 401."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        pool.fetchrow.return_value = None

        req = _build_request("forged-token")
        resp = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_disabled_user_returns_401(self):
        """Disabled user account -> 401 even with a valid-looking session."""
        from src.services.dashboard.v2.auth import refresh

        pool = FakePool()
        disabled = _valid_session_row()
        disabled["disabled"] = True
        pool.fetchrow.return_value = disabled

        req = _build_request("disabled-user-token")
        resp = MagicMock()

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401


# ---------------------------------------------------------------------------
# Logout — UC-RT-03
# ---------------------------------------------------------------------------

class TestLogoutRevokesSession:
    @pytest.mark.asyncio
    async def test_logout_marks_session_revoked_and_clears_cookies(self):
        """TC-19-03: logout sets revoked_at on the session row and clears cookies."""
        from src.services.dashboard.v2.auth import logout
        from src.services.dashboard.v2._deps import Principal

        pool = FakePool()
        pool.execute = AsyncMock(return_value="UPDATE 1")

        req = _build_request("active-refresh")
        resp = MagicMock()
        resp.delete_cookie = MagicMock()
        principal = Principal(
            user_id=42, email="user@example.com", role="owner",
            source="v2_jwt", workspace_id=1,
        )

        with _pool_ctx(pool):
            res = await logout(request=req, response=resp, body=None, _=principal)

        assert res == {"status": "ok"}
        # Session UPDATE issued
        pool.execute.assert_awaited_once()
        sql = pool.execute.await_args.args[0]
        assert "UPDATE sessions SET revoked_at" in sql
        # Cookies cleared on response
        assert resp.delete_cookie.call_count >= 1
