"""Unit tests for forgot-password / reset-password flow (Story #18).

Covers test plan #33 (TC-18-*). Verifies:
- Slack webhook delivery with correct link + 1h TTL
- No email enumeration (registered vs unregistered identical responses)
- Token never exposed in HTTP response when ENVIRONMENT_MODE=production
- Reset honors used_at + expires_at; all user sessions revoked on success
- FRONTEND_URL env propagates into the Slack link
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "src.services.dashboard.v2.auth"


def _pool_ctx(pool):
    """Patch the module-local get_pool in auth.py to return our fake."""
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _httpx_ctx(post_mock: AsyncMock):
    """Patch httpx.AsyncClient so the test can observe Slack POSTs without
    network access. The auth module does `import httpx` inside the function
    body, so we patch the package symbol."""
    fake_client = MagicMock()
    fake_client.post = post_mock
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient = MagicMock(return_value=fake_client)
    return patch.dict("sys.modules", {"httpx": fake_httpx})


# ---------------------------------------------------------------------------
# /forgot — UC-FP-01, UC-FP-02, UC-FP-05
# ---------------------------------------------------------------------------

class TestForgot:
    @pytest.mark.asyncio
    async def test_forgot_known_email_sends_slack_and_returns_token_in_test_mode(self):
        """TC-18-01 + TC-18-05: known email -> Slack POST + token in body (test mode)."""
        from src.services.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=42)
        post = AsyncMock()

        env = {
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T0/B0/XYZ",
            "FRONTEND_URL": "https://dash.autoniix.com",
            "ENVIRONMENT_MODE": "test",
        }
        with _pool_ctx(pool), _httpx_ctx(post), patch.dict(os.environ, env, clear=False):
            res = await forgot(ForgotIn(email="alice@example.com"))

        assert res["status"] == "ok"
        # TC-18-13 inverse: in test mode the token IS returned for testability
        assert "reset_token" in res and len(res["reset_token"]) > 20
        # TC-18-14: SQL uses 1 hour TTL
        insert_sql = pool.execute.await_args.args[0]
        assert "1 hour" in insert_sql.lower()
        # TC-18-11: Slack POST hit our webhook with the FRONTEND_URL link
        post.assert_awaited_once()
        webhook_arg, = post.await_args.args
        assert webhook_arg == env["SLACK_WEBHOOK_URL"]
        payload = post.await_args.kwargs["json"]
        assert "https://dash.autoniix.com/reset-password?token=" in payload["text"]
        assert "expires in 1 hour" in payload["text"]

    @pytest.mark.asyncio
    async def test_forgot_unknown_email_returns_ok_without_slack_post(self):
        """TC-18-05 + TC-18-15: unknown email -> 200 ok, NO Slack POST, NO DB write."""
        from src.services.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = None  # user not found
        post = AsyncMock()

        env = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T0/B0/XYZ"}
        with _pool_ctx(pool), _httpx_ctx(post), patch.dict(os.environ, env, clear=False):
            res = await forgot(ForgotIn(email="nobody@example.com"))

        # Identical surface to known-email response (no enumeration)
        assert res == {"status": "ok"}
        post.assert_not_awaited()
        pool.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forgot_in_production_does_not_return_token(self):
        """TC-18-13: production mode never exposes the token in HTTP response."""
        from src.services.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=7)
        post = AsyncMock()

        env = {
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T0/B0/XYZ",
            "ENVIRONMENT_MODE": "production",
        }
        with _pool_ctx(pool), _httpx_ctx(post), patch.dict(os.environ, env, clear=False):
            res = await forgot(ForgotIn(email="bob@example.com"))

        assert res == {"status": "ok"}
        assert "reset_token" not in res
        post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_forgot_without_slack_webhook_still_succeeds(self):
        """AC: graceful fallback when SLACK_WEBHOOK_URL is unset."""
        from src.services.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=1)
        post = AsyncMock()

        env_keys_to_clear = {"SLACK_WEBHOOK_URL": ""}
        with _pool_ctx(pool), _httpx_ctx(post), \
             patch.dict(os.environ, env_keys_to_clear, clear=False):
            # Force unset (patch.dict with empty string doesn't unset; pop instead)
            saved = os.environ.pop("SLACK_WEBHOOK_URL", None)
            try:
                res = await forgot(ForgotIn(email="carol@example.com"))
            finally:
                if saved is not None:
                    os.environ["SLACK_WEBHOOK_URL"] = saved

        assert res["status"] == "ok"
        post.assert_not_awaited()  # no webhook -> no POST attempt

    @pytest.mark.asyncio
    async def test_forgot_slack_post_failure_does_not_break_endpoint(self):
        """AC: Slack delivery failure must NOT bubble up; user still sees 200 ok."""
        from src.services.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=99)
        post = AsyncMock(side_effect=RuntimeError("Slack down"))

        env = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T0/B0/XYZ"}
        with _pool_ctx(pool), _httpx_ctx(post), patch.dict(os.environ, env, clear=False):
            res = await forgot(ForgotIn(email="dave@example.com"))

        assert res["status"] == "ok"
        post.assert_awaited_once()  # we did try


# ---------------------------------------------------------------------------
# /reset — UC-FP-03, UC-FP-04
# ---------------------------------------------------------------------------

class TestReset:
    @pytest.mark.asyncio
    async def test_reset_valid_token_updates_password_and_revokes_sessions(self):
        """TC-18-03: valid token -> password updated + sessions revoked + token marked used."""
        from src.services.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            used_at=None,
        )

        # The endpoint enters `async with pool.acquire() as conn: async with conn.transaction():`
        # so we need acquire() to return an async context manager wrapping a conn that
        # also exposes transaction() as an async context manager. Build that here.
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        tx = MagicMock()
        tx.__aenter__ = AsyncMock(return_value=None)
        tx.__aexit__ = AsyncMock(return_value=None)
        conn.transaction = MagicMock(return_value=tx)
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=acquire_cm)

        with _pool_ctx(pool):
            res = await reset(ResetIn(token="a" * 32, password="N3wPassword!"))

        assert res == {"status": "ok"}
        # 3 statements: update users, mark reset used, revoke sessions
        assert conn.execute.await_count == 3
        sqls = [call.args[0] for call in conn.execute.await_args_list]
        assert any("UPDATE users SET password_hash" in s for s in sqls)
        assert any("password_resets SET used_at" in s.lower().replace("  ", " ") for s in sqls) \
               or any("UPDATE password_resets" in s for s in sqls)
        assert any("UPDATE sessions SET revoked_at" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_reset_unknown_token_returns_400(self):
        """TC-18-06: token not in DB -> 400."""
        from src.services.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = None

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await reset(ResetIn(token="bogus" + "x" * 27, password="N3wPassword!"))

        assert ei.value.status_code == 400
        assert "invalid" in ei.value.detail.lower() or "expired" in ei.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reset_expired_token_returns_400(self):
        """TC-18-07: expires_at in the past -> 400."""
        from src.services.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            used_at=None,
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await reset(ResetIn(token="a" * 32, password="N3wPassword!"))
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_already_used_token_returns_400(self):
        """TC-18-09: used_at populated -> 400 (single-use enforcement)."""
        from src.services.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            used_at=datetime.utcnow() - timedelta(minutes=5),
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await reset(ResetIn(token="a" * 32, password="N3wPassword!"))
        assert ei.value.status_code == 400

    def test_reset_password_min_length_validation(self):
        """TC-18-08: short password caught by Pydantic Field(min_length=8)."""
        from src.services.dashboard.v2.auth import ResetIn
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResetIn(token="anytoken", password="short")
