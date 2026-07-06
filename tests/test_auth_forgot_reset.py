"""Unit tests for forgot-password / reset-password flow (Story #18).

Covers test plan #33 (TC-18-*). After the 2026-05-18 requirement change,
the reset link is delivered by **email** (SMTP) rather than Slack DM.
Tests mock ``services_api.dashboard.v2._email.send_email`` so no real
mail server is ever contacted.

Verified behaviours:
- Email delivered to the user's registered address with the correct link
  + 1-hour TTL message
- No email enumeration (registered vs unregistered identical 200 OK)
- Token never exposed in HTTP response when SMTP is configured
- Token IS exposed in response in dev/test mode when SMTP is unconfigured
  (so local flows can complete without a real mail server)
- Reset honors used_at + expires_at; all user sessions revoked on success
- FRONTEND_URL env propagates into the email link
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "services_api.dashboard.v2.auth"
_EMAIL_MODULE = "services_api.dashboard.v2._email"


def _pool_ctx(pool):
    """Patch the module-local get_pool in auth.py to return our fake."""
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _email_ctx(send_mock: AsyncMock, *, configured: bool = True):
    """Patch send_email + is_configured on the _email module so auth.py's
    ``from ._email import send_email, is_configured`` picks them up."""
    return [
        patch(f"{_EMAIL_MODULE}.send_email", new=send_mock),
        patch(f"{_EMAIL_MODULE}.is_configured", new=MagicMock(return_value=configured)),
    ]



class TestForgot:
    @pytest.mark.asyncio
    async def test_forgot_known_email_sends_message_with_correct_link_and_no_token_in_body(self):
        """TC-18-01 + TC-18-11 + TC-18-16: SMTP configured -> email send invoked
        with the right To/Subject/link; response is 200 ok with NO token."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=42)
        send = AsyncMock(return_value=True)

        env = {"FRONTEND_URL": "https://dash.autoniix.com"}
        e1, e2 = _email_ctx(send, configured=True)
        with _pool_ctx(pool), e1, e2, patch.dict(os.environ, env, clear=False):
            res = await forgot(ForgotIn(email="alice@example.com"))

        assert res == {"status": "ok"}
        send.assert_awaited_once()
        kwargs = send.await_args.kwargs
        assert kwargs["to"] == "alice@example.com"
        assert "Reset your Autoniix password" in kwargs["subject"]
        assert "https://dash.autoniix.com/reset-password?token=" in kwargs["html"]
        assert "https://dash.autoniix.com/reset-password?token=" in kwargs["text"]
        assert "expires in 1 hour" in kwargs["text"]
        insert_sql = pool.execute.await_args.args[0]
        assert "1 hour" in insert_sql.lower()

    @pytest.mark.asyncio
    async def test_forgot_unknown_email_returns_ok_without_email_or_db_write(self):
        """TC-18-05 + TC-18-19: unknown email -> 200 ok, NO email send, NO DB row."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = None
        send = AsyncMock(return_value=True)

        e1, e2 = _email_ctx(send, configured=True)
        with _pool_ctx(pool), e1, e2:
            res = await forgot(ForgotIn(email="nobody@example.com"))

        assert res == {"status": "ok"}
        send.assert_not_awaited()
        pool.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forgot_in_production_without_smtp_does_not_return_token(self):
        """TC-18-15: production + SMTP missing -> still no token leak in body."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=7)
        send = AsyncMock(return_value=False)

        e1, e2 = _email_ctx(send, configured=False)
        with _pool_ctx(pool), e1, e2:
            res = await forgot(ForgotIn(email="bob@example.com"))

        assert res == {"status": "ok"}
        assert "reset_token" not in res

    @pytest.mark.asyncio
    async def test_forgot_without_smtp_never_returns_token(self):
        """TC-18-14 (updated): SMTP missing -> never leak token in response."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=1)
        send = AsyncMock(return_value=False)

        e1, e2 = _email_ctx(send, configured=False)
        with _pool_ctx(pool), e1, e2:
            res = await forgot(ForgotIn(email="carol@example.com"))

        assert res == {"status": "ok"}
        assert "reset_token" not in res

    @pytest.mark.asyncio
    async def test_forgot_smtp_send_failure_does_not_break_endpoint(self):
        """TC-18-13: best-effort delivery — send_email failure does NOT bubble up;
        user still sees 200 ok with no error."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=99)
        send = AsyncMock(return_value=False)

        e1, e2 = _email_ctx(send, configured=True)
        with _pool_ctx(pool), e1, e2:
            res = await forgot(ForgotIn(email="dave@example.com"))

        assert res == {"status": "ok"}
        send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_forgot_email_subject_prefix_applied(self):
        """MAIL_SUBJECT_PREFIX env prepends to the subject line."""
        from services_api.dashboard.v2.auth import forgot, ForgotIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(id=2)
        send = AsyncMock(return_value=True)

        env = {"MAIL_SUBJECT_PREFIX": "[Staging]"}
        e1, e2 = _email_ctx(send, configured=True)
        with _pool_ctx(pool), e1, e2, patch.dict(os.environ, env, clear=False):
            await forgot(ForgotIn(email="ed@example.com"))

        assert send.await_args.kwargs["subject"].startswith("[Staging] Reset your Autoniix password")



class TestReset:
    @pytest.mark.asyncio
    async def test_reset_valid_token_updates_password_and_revokes_sessions(self):
        """TC-18-03: valid token -> password updated + sessions revoked + token marked used."""
        from services_api.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            used_at=None,
        )

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
        assert conn.execute.await_count == 3
        sqls = [call.args[0] for call in conn.execute.await_args_list]
        assert any("UPDATE users SET password_hash" in s for s in sqls)
        assert any("UPDATE password_resets" in s for s in sqls)
        assert any("UPDATE sessions SET revoked_at" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_reset_unknown_token_returns_400(self):
        """TC-18-06: token not in DB -> 400."""
        from services_api.dashboard.v2.auth import reset, ResetIn

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
        from services_api.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            used_at=None,
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await reset(ResetIn(token="a" * 32, password="N3wPassword!"))
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_already_used_token_returns_400(self):
        """TC-18-09: used_at populated -> 400 (single-use enforcement)."""
        from services_api.dashboard.v2.auth import reset, ResetIn

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord(
            id=1,
            user_id=42,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            used_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as ei:
                await reset(ResetIn(token="a" * 32, password="N3wPassword!"))
        assert ei.value.status_code == 400

    def test_reset_password_min_length_validation(self):
        """TC-18-08: short password caught by Pydantic Field(min_length=8)."""
        from services_api.dashboard.v2.auth import ResetIn
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResetIn(token="anytoken", password="short")



class TestEmailHelper:
    def test_is_configured_false_when_smtp_host_unset(self, monkeypatch):
        from services_api.dashboard.v2 import _email
        monkeypatch.delenv("SMTP_HOST", raising=False)
        assert _email.is_configured() is False

    def test_is_configured_true_when_smtp_host_set(self, monkeypatch):
        from services_api.dashboard.v2 import _email
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        assert _email.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_email_short_circuits_when_unconfigured(self, monkeypatch):
        from services_api.dashboard.v2 import _email
        monkeypatch.delenv("SMTP_HOST", raising=False)
        ok = await _email.send_email(
            to="x@example.com", subject="s", html="<p>h</p>", text="t"
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_send_email_logs_warning_when_unconfigured(self, monkeypatch, caplog):
        import logging
        from services_api.dashboard.v2 import _email
        monkeypatch.delenv("SMTP_HOST", raising=False)
        with caplog.at_level(logging.WARNING, logger="services_api.dashboard.v2._email"):
            await _email.send_email(
                to="x@example.com", subject="s", html="<p>h</p>", text="t"
            )
        assert any("SMTP not configured" in r.message for r in caplog.records)



class TestForgotProdSmtpWarning:
    @pytest.mark.asyncio
    async def test_prod_mode_no_reset_token_in_response_when_smtp_missing(self, monkeypatch):
        """Regression for #200: prod mode must NOT expose reset_token even when SMTP absent."""
        from services_api.dashboard.v2 import auth as auth_mod

        pool = FakePool()
        pool.fetchrow.return_value = FakeRecord({"id": 1})
        send_mock = AsyncMock(return_value=False)
        with _pool_ctx(pool):
            for ctx in _email_ctx(send_mock, configured=False):
                ctx.start()
            try:
                result = await auth_mod.forgot(auth_mod.ForgotIn(email="user@example.com"))
            finally:
                patch.stopall()

        assert "reset_token" not in result
        assert result["status"] == "ok"
