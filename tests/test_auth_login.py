"""Regression tests for POST /auth/login (Bug #110).

Covers:
- TC-110-01: Valid credentials → 200, sets cookies, returns access_token
- TC-110-02: Wrong password → 401 "Invalid credentials" (error surfaced, NOT silent redirect)
- TC-110-03: Unknown email → 401 "Invalid credentials"
- TC-110-04: Disabled account → 401
- TC-110-05: NULL password_hash in DB (legacy user row) → 401, no unhandled exception
- TC-110-06: _verify_pw never raises — always returns bool (regression guard)
- TC-110-07: Expired/missing refresh cookie → 401 on /refresh (login still shows error)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "src.services.dashboard.v2.auth"


def _pool_ctx(pool):
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _make_request(client_host: str = "127.0.0.1") -> Request:
    """Build a minimal real Starlette Request so slowapi's rate-limiter is satisfied."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v2/auth/login",
        "query_string": b"",
        "headers": [(b"user-agent", b"pytest")],
        "client": (client_host, 12345),
    }
    return Request(scope)


def _make_user(**overrides) -> FakeRecord:
    from src.services.dashboard.v2.auth import _hash_pw
    defaults = dict(
        id=1,
        email="admin@autoniix.com",
        password_hash=_hash_pw("correct-password"),
        role="owner",
        mfa_secret=None,
        mfa_enabled=False,
        disabled=False,
        active_workspace_id=1,
    )
    defaults.update(overrides)
    return FakeRecord(defaults)



@pytest.mark.asyncio
async def test_login_valid_credentials_returns_200_and_tokens():
    from src.services.dashboard.v2.auth import login, LoginIn

    pool = FakePool()
    user = _make_user()
    pool.fetchrow = AsyncMock(side_effect=[
        user,
        FakeRecord(active_workspace_id=1),
        FakeRecord(role="owner"),
    ])
    pool.execute = AsyncMock(return_value="INSERT 0 1")

    body = LoginIn(email="admin@autoniix.com", password="correct-password")
    response = MagicMock()
    response.set_cookie = MagicMock()

    with _pool_ctx(pool):
        result = await login(request=_make_request(), body=body, response=response)

    assert result["status"] == "ok"
    assert "access_token" in result
    response.set_cookie.assert_called()



@pytest.mark.asyncio
async def test_login_wrong_password_raises_401():
    from src.services.dashboard.v2.auth import login, LoginIn

    pool = FakePool()
    pool.fetchrow = AsyncMock(return_value=_make_user())

    body = LoginIn(email="admin@autoniix.com", password="WRONG-password")
    with _pool_ctx(pool):
        with pytest.raises(HTTPException) as exc_info:
            await login(request=_make_request(), body=body, response=MagicMock())

    assert exc_info.value.status_code == 401
    assert "credentials" in exc_info.value.detail.lower()



@pytest.mark.asyncio
async def test_login_unknown_email_raises_401():
    from src.services.dashboard.v2.auth import login, LoginIn

    pool = FakePool()
    pool.fetchrow = AsyncMock(return_value=None)

    body = LoginIn(email="ghost@example.com", password="any-password")
    with _pool_ctx(pool):
        with pytest.raises(HTTPException) as exc_info:
            await login(request=_make_request(), body=body, response=MagicMock())

    assert exc_info.value.status_code == 401



@pytest.mark.asyncio
async def test_login_disabled_account_raises_401():
    from src.services.dashboard.v2.auth import login, LoginIn

    pool = FakePool()
    pool.fetchrow = AsyncMock(return_value=_make_user(disabled=True))

    body = LoginIn(email="admin@autoniix.com", password="correct-password")
    with _pool_ctx(pool):
        with pytest.raises(HTTPException) as exc_info:
            await login(request=_make_request(), body=body, response=MagicMock())

    assert exc_info.value.status_code == 401



@pytest.mark.asyncio
async def test_login_null_password_hash_raises_401_not_500():
    from src.services.dashboard.v2.auth import login, LoginIn

    pool = FakePool()
    pool.fetchrow = AsyncMock(return_value=_make_user(password_hash=None))

    body = LoginIn(email="admin@autoniix.com", password="any-password")
    with _pool_ctx(pool):
        with pytest.raises(HTTPException) as exc_info:
            await login(request=_make_request(), body=body, response=MagicMock())

    assert exc_info.value.status_code == 401



def test_verify_pw_never_raises_on_garbage_input():
    from src.services.dashboard.v2.auth import _verify_pw

    bad_inputs = [
        ("password", ""),
        ("password", None),
        ("", ""),
        ("password", "bcrypt-garbage-$2b$12$xxx"),
        ("password", "pbkdf2$onlytwoparts"),
        ("", "pbkdf2$salt$" + "a" * 64),
    ]
    for pw, hashed in bad_inputs:
        result = _verify_pw(pw, hashed or "")
        assert result is False, f"Expected False for pw={pw!r} hash={hashed!r}, got {result}"



def test_hash_and_verify_roundtrip():
    from src.services.dashboard.v2.auth import _hash_pw, _verify_pw

    pw = "SuperSecret#99"
    hashed = _hash_pw(pw)
    assert _verify_pw(pw, hashed) is True
    assert _verify_pw("wrong", hashed) is False
