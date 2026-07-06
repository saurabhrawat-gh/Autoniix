"""Unit tests for refresh token rotation (Story #19).

Covers test plan #32 (TC-19-*). Verifies:
- Each /refresh marks the old session row `rotated_at=NOW()` AND inserts a new row
- Replayed (already-rotated) refresh tokens return 401
- Expired / revoked / disabled-user / missing-token paths return 401
- New access_token + new refresh cookie issued on success
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "services_api.dashboard.v2.auth"


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
        expires_at=datetime.now(timezone.utc) + timedelta(days=15),
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



class TestRefreshHappyPath:
    @pytest.mark.asyncio
    async def test_refresh_marks_old_session_rotated_and_inserts_new(self):
        """TC-19-01 + TC-19-11: success path marks old row rotated and inserts new row."""
        from services_api.dashboard.v2.auth import refresh

        pool = FakePool()
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
        assert conn_execute.await_count == 2
        sqls = [c.args[0] for c in conn_execute.await_args_list]
        assert any("UPDATE sessions SET rotated_at=NOW()" in s for s in sqls)
        assert any("INSERT INTO sessions" in s for s in sqls)
        assert resp.set_cookie.call_count >= 2



class TestRefreshNoWorkspace:
    @pytest.mark.asyncio
    async def test_refresh_no_workspace_returns_wid_zero_not_one(self):
        """Regression: refresh with active_workspace_id=None must not fall back to wid=1 (AE-217)."""
        from services_api.dashboard.v2.auth import refresh

        pool = FakePool()
        pool.fetchrow.side_effect = [
            _valid_session_row(),
            FakeRecord(active_workspace_id=None),
        ]

        conn_execute = AsyncMock(return_value="UPDATE 1")
        pool.acquire = MagicMock(return_value=_build_acquire(conn_execute))

        req = _build_request("rawrefreshtoken")
        resp = MagicMock()
        resp.set_cookie = MagicMock()

        with _pool_ctx(pool):
            result = await refresh(request=req, response=resp, body=None)

        assert result["status"] == "ok"
        import jwt as _jwt, os
        token = result["access_token"]
        payload = _jwt.decode(token, os.environ["AUTH_JWT_SECRET"], algorithms=["HS256"])
        assert payload["wid"] == 0, f"Expected wid=0, got wid={payload['wid']} (regression: AE-217)"


class TestRefreshRejected:
    @pytest.mark.asyncio
    async def test_refresh_missing_cookie_and_body_returns_401(self):
        """No refresh token anywhere -> 401."""
        from services_api.dashboard.v2.auth import refresh

        req = _build_request(None)
        resp = MagicMock()

        with pytest.raises(HTTPException) as ei:
            await refresh(request=req, response=resp, body=None)
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_replay_of_rotated_token_returns_401(self):
        """TC-19-04 + TC-19-12: token already rotated -> 401 (replay attack)."""
        from services_api.dashboard.v2.auth import refresh

        pool = FakePool()
        rotated_row = _valid_session_row()
        rotated_row["rotated_at"] = datetime.now(timezone.utc) - timedelta(seconds=30)
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
        from services_api.dashboard.v2.auth import refresh

        pool = FakePool()
        expired = _valid_session_row()
        expired["expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
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
        from services_api.dashboard.v2.auth import refresh

        pool = FakePool()
        revoked = _valid_session_row()
        revoked["revoked_at"] = datetime.now(timezone.utc) - timedelta(minutes=5)
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
        from services_api.dashboard.v2.auth import refresh

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
        from services_api.dashboard.v2.auth import refresh

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



class TestLogoutRevokesSession:
    @pytest.mark.asyncio
    async def test_logout_marks_session_revoked_and_clears_cookies(self):
        """TC-19-03: logout sets revoked_at on the session row and clears cookies."""
        from services_api.dashboard.v2.auth import logout
        from services_api.dashboard.v2._deps import Principal

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
        pool.execute.assert_awaited_once()
        sql = pool.execute.await_args.args[0]
        assert "UPDATE sessions SET revoked_at" in sql
        assert resp.delete_cookie.call_count >= 1
