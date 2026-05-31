"""Regression tests for POST /auth/register (Bug AE-264 / #308).

Privilege escalation guard: only the very first user in the system bootstraps
as global owner. Every subsequent self-registrant must default to ``viewer``
so that random visitors to the public ``/register`` form cannot grant
themselves admin permissions.

Test cases:
- TC-264-01: First user (empty users table) → users.role = 'owner'
- TC-264-02: Second user (one existing user) → users.role = 'viewer'
- TC-264-03: Nth user (many existing users) → users.role = 'viewer'
- TC-264-04: Duplicate email → 409 (no INSERT, no role assignment)
- TC-264-05: workspace_members.role is always 'owner' for the new workspace
  the registrant just created (independent of global users.role).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tests.conftest import FakePool

_AUTH_MODULE = "src.services.dashboard.v2.auth"


def _pool_ctx(pool):
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v2/auth/register",
        "query_string": b"",
        "headers": [(b"user-agent", b"pytest")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def _build_pool(*, existing_user_count: int, email_exists: bool = False):
    """Build a FakePool whose ``acquire()`` yields a connection that drives
    register() through its happy path with the given preconditions.

    fetchval call sequence inside register():
      1. SELECT id FROM users WHERE lower(email)=lower($1)   → email_exists?
      2. SELECT COUNT(*) FROM users                          → existing_user_count
      3. INSERT INTO users RETURNING id                      → 42
      4. SELECT id FROM workspaces WHERE slug=$1             → None (no collision)
      5. INSERT INTO workspaces RETURNING id                 → 100
    """
    pool = FakePool()
    conn = MagicMock()
    conn.fetchval = AsyncMock(side_effect=[
        1 if email_exists else None,
        existing_user_count,
        42,
        None,
        100,
    ])
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    @asynccontextmanager
    async def _txn():
        yield None

    conn.transaction = MagicMock(side_effect=_txn)

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = MagicMock(side_effect=_acquire)
    return pool, conn


def _insert_role_arg(conn) -> str:
    """Extract the ``role`` positional arg passed to the users INSERT.

    register() calls conn.fetchval(sql, email, display_name, pw_hash, role, token).
    The role is the 4th positional arg (index 4 because the SQL is index 0).
    """
    for call in conn.fetchval.await_args_list:
        sql = call.args[0] if call.args else ""
        if "INSERT INTO users" in sql:
            # args = (sql, email, display_name, pw_hash, role, verify_token)
            return call.args[4]
    raise AssertionError("INSERT INTO users was never called")


def _workspace_member_role_arg(conn) -> str:
    """Extract the role literal embedded in the workspace_members INSERT."""
    for call in conn.execute.await_args_list:
        sql = call.args[0] if call.args else ""
        if "INSERT INTO workspace_members" in sql:
            return "owner" if "'owner'" in sql else "<unknown>"
    raise AssertionError("INSERT INTO workspace_members was never called")


# ── TC-264-01 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_user_registration_assigns_owner_role():
    """When the users table is empty, the first registrant bootstraps as
    global owner. This is the only path that should ever produce role=owner
    via the public /register form."""
    from src.services.dashboard.v2.auth import register, RegisterIn

    pool, conn = _build_pool(existing_user_count=0)
    body = RegisterIn(
        email="founder@autoniix.com",
        password="strong-pass-1234",
        workspace_name="Roar Studios",
    )

    with _pool_ctx(pool), patch("src.services.dashboard.v2._resend.send_email"):
        result = await register(body=body, request=_make_request())

    assert _insert_role_arg(conn) == "owner", (
        "First user must be granted global owner role"
    )
    assert result["status"] == "ok"


# ── TC-264-02 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_second_user_registration_assigns_viewer_role():
    """When at least one user already exists, every subsequent self-registrant
    must default to viewer. This is the privilege-escalation guard."""
    from src.services.dashboard.v2.auth import register, RegisterIn

    pool, conn = _build_pool(existing_user_count=1)
    body = RegisterIn(
        email="random+1@example.com",
        password="strong-pass-1234",
        workspace_name="Random Workspace",
    )

    with _pool_ctx(pool), patch("src.services.dashboard.v2._resend.send_email"):
        await register(body=body, request=_make_request())

    role = _insert_role_arg(conn)
    assert role == "viewer", (
        f"Second registrant must be viewer (got {role!r}). "
        "Anything else is a privilege escalation regression."
    )


# ── TC-264-03 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("existing_count", [2, 3, 10, 1_000])
async def test_nth_user_registration_assigns_viewer_role(existing_count: int):
    """Sanity: the viewer-default behaviour holds for any non-zero existing
    user count, not just exactly one."""
    from src.services.dashboard.v2.auth import register, RegisterIn

    pool, conn = _build_pool(existing_user_count=existing_count)
    body = RegisterIn(
        email=f"random+{existing_count}@example.com",
        password="strong-pass-1234",
        workspace_name=f"Workspace {existing_count}",
    )

    with _pool_ctx(pool), patch("src.services.dashboard.v2._resend.send_email"):
        await register(body=body, request=_make_request())

    assert _insert_role_arg(conn) == "viewer"


# ── TC-264-04 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_email_raises_409_and_inserts_nothing():
    """Existing email → 409 before any role assignment. Regression guard
    that the first-user check does not run on the duplicate path."""
    from src.services.dashboard.v2.auth import register, RegisterIn

    pool, conn = _build_pool(existing_user_count=0, email_exists=True)
    body = RegisterIn(
        email="founder@autoniix.com",
        password="strong-pass-1234",
        workspace_name="Roar Studios",
    )

    with _pool_ctx(pool), pytest.raises(HTTPException) as exc:
        await register(body=body, request=_make_request())

    assert exc.value.status_code == 409
    # No INSERT INTO users should have happened
    insert_user_calls = [
        c for c in conn.fetchval.await_args_list
        if c.args and "INSERT INTO users" in c.args[0]
    ]
    assert insert_user_calls == [], "Duplicate email path must not insert"


# ── TC-264-05 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workspace_member_role_is_always_owner_for_own_workspace():
    """The privilege guard only touches the *global* users.role column.
    Every registrant still owns the workspace they just created — this is
    enforced by the literal 'owner' in the workspace_members INSERT.
    Regression guard so we never accidentally weaken this."""
    from src.services.dashboard.v2.auth import register, RegisterIn

    pool, conn = _build_pool(existing_user_count=5)  # not first user
    body = RegisterIn(
        email="member@example.com",
        password="strong-pass-1234",
        workspace_name="My Space",
    )

    with _pool_ctx(pool), patch("src.services.dashboard.v2._resend.send_email"):
        await register(body=body, request=_make_request())

    # Global role: viewer (privilege guard)
    assert _insert_role_arg(conn) == "viewer"
    # Workspace-scoped role for the brand-new workspace: owner (unchanged)
    assert _workspace_member_role_arg(conn) == "owner"
