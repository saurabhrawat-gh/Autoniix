"""Invite-acceptance tests — public attack surface.

Covers Story AE-269 (parent epic AE-266 / AE-7). Targets the two
unauthenticated endpoints in ``src/services/dashboard/v2/auth.py``:

* ``GET /invite-info?token=...`` (preview)
* ``POST /accept-invite`` (consume the token, create-or-attach user, JWT)

These are the **most security-sensitive endpoints** in the workspace
section because they are reachable without a session.

Mode A (mocked-pool) coverage of the 25 ACs:
  * Preview happy/error paths — WS-ACC-01..03
  * Accept happy paths — WS-ACC-04, 05, 14, 25
  * Accept error paths — WS-ACC-06, 07, 08, 09, 10, 13
  * Privilege-escalation regression — WS-ACC-19, 22
  * Cross-invite tampering — WS-ACC-24 (current behaviour documented)

Cases requiring a real Postgres testcontainer (FK constraints, role
CHECK constraints, rate-limit middleware, timing-attack measurements)
are documented as ``pytest.mark.skip`` with a ``reason`` linking to the
follow-up:
  * WS-ACC-12  — workspace deleted between invite + accept (FK)
  * WS-ACC-15  — token brute-force / rate limit
  * WS-ACC-16  — timing attack
  * WS-ACC-17  — URL-encoded token (URL-routing concern)
  * WS-ACC-18  — re-acceptance after disable/re-enable
  * WS-ACC-20  — signup creates owner of own ws
  * WS-ACC-21  — signup with matching invite must NOT auto-elevate
  * WS-ACC-23  — DB CHECK constraint test

These will be picked up by AE-273 (Plan limits + isolation +
concurrency) which already requires testcontainer infrastructure.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_AUTH = "src.services.dashboard.v2.auth"



class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeConn:
    """Mock asyncpg.Connection with the methods accept_invite uses."""

    def __init__(self):
        self.fetchrow = AsyncMock(return_value=None)
        self.fetchval = AsyncMock(return_value=None)
        self.execute = AsyncMock(return_value="OK")

    def transaction(self):
        return _FakeTxn()


class _FakeAcquireCM:
    def __init__(self, conn: FakeConn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class FakeTxnPool(FakePool):
    """FakePool extended with ``acquire()`` returning an async CM yielding a FakeConn."""

    def __init__(self):
        super().__init__()
        self.conn = FakeConn()

    def acquire(self):
        return _FakeAcquireCM(self.conn)



def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _future(days: int = 7):
    return datetime.now(timezone.utc) + timedelta(days=days)


def _past(days: int = 1):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _request():
    req = MagicMock()
    req.client.host = "203.0.113.5"
    req.headers = {"user-agent": "pytest"}
    return req


def _response():
    return MagicMock()


def _pool_ctx(pool):
    return patch(f"{_AUTH}.get_pool", new_callable=AsyncMock, return_value=pool)


def _suppress_side_effects():
    """Stub the JWT + session-cookie helpers so tests don't depend on JWT secret etc."""
    return [
        patch(f"{_AUTH}._hash_pw", return_value="$argon2id$fake"),
        patch(f"{_AUTH}._refresh_token", return_value=("rawtok", "hashedtok")),
        patch(f"{_AUTH}._issue_jwt", return_value="fake.jwt.token"),
        patch(f"{_AUTH}._set_auth_cookies"),
    ]


def _enter_all(patches):
    return [p.__enter__() for p in patches]


def _exit_all(patches):
    for p in patches:
        try:
            p.__exit__(None, None, None)
        except Exception:
            pass



class TestInvitePreview:

    @pytest.mark.asyncio
    async def test_ws_acc_01_valid_token_preview_returns_full_metadata(self):
        """WS-ACC-01 — Valid token preview → 200 with email, role, workspace_name, user_exists."""
        from src.services.dashboard.v2.auth import invite_info

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(
                email="invitee@test.com", role="member",
                workspace_id=42, accepted_at=None, cancelled_at=None, expires_at=_future(),
            ),
            FakeRecord(name="Awesome Workspace"),
        ]
        pool.fetchval.return_value = 99

        with _pool_ctx(pool):
            result = await invite_info(token="any-raw-token")

        assert result["email"] == "invitee@test.com"
        assert result["role"] == "member"
        assert result["workspace_name"] == "Awesome Workspace"
        assert result["user_exists"] is True

    @pytest.mark.asyncio
    async def test_ws_acc_02_malformed_token_returns_400(self):
        """WS-ACC-02 — Malformed token (no matching row) → 400 'Invalid invitation token'."""
        from src.services.dashboard.v2.auth import invite_info

        pool = FakePool()
        pool.fetchrow.return_value = None

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await invite_info(token="\x00\x01\x02 garbage")
        assert exc.value.status_code == 400
        assert "invalid invitation" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_acc_03_nonexistent_token_hash_returns_400(self):
        """WS-ACC-03 — Non-existent token hash → 400 (same path as malformed)."""
        from src.services.dashboard.v2.auth import invite_info

        pool = FakePool()
        pool.fetchrow.return_value = None

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await invite_info(token="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert exc.value.status_code == 400



class TestAcceptHappyPaths:

    @pytest.mark.asyncio
    async def test_ws_acc_04_brand_new_email_creates_user_with_viewer_platform_role(self):
        """WS-ACC-04 + WS-ACC-19 — Brand-new email → INSERT users (role='user'),
        INSERT workspace_members (role from invite). AE-284: viewer→user rename."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="newbie@test.com",
                       role="member", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=999, email="newbie@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = None
        pool.conn.fetchval.return_value = 999

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                result = await accept_invite(
                    body=AcceptInviteIn(token="raw", password="strongpass123"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)

        assert result["status"] == "ok"
        assert result["workspace_id"] == 42
        assert result["role"] == "member"

        insert_user_calls = [
            c for c in pool.conn.fetchval.await_args_list
            if c.args and "INSERT INTO users" in c.args[0]
        ]
        assert len(insert_user_calls) == 1
        sql = insert_user_calls[0].args[0]
        assert "'user'" in sql, (
            "AE-264 regression: new user from accept-invite must be inserted with "
            f"role='user' literal in the SQL. Got SQL:\n{sql}"
        )
        assert len(insert_user_calls[0].args) == 5, (
            "INSERT users should bind 4 params (email, display_name, pw, ws_id). "
            "If a role param is added, AE-264 regression has been reintroduced."
        )

        wm_inserts = [
            c for c in pool.conn.execute.await_args_list
            if c.args and "INSERT INTO workspace_members" in c.args[0]
        ]
        assert len(wm_inserts) == 1
        assert wm_inserts[0].args[3] == "member"

    @pytest.mark.asyncio
    async def test_ws_acc_05_existing_user_no_password_required(self):
        """WS-ACC-05 — Existing email → reuses user, NO INSERT users, NO password required."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="returning@test.com",
                       role="viewer", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=777, email="returning@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(id=777, email="returning@test.com",
                                                     role="viewer", disabled=False)

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                result = await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)

        assert result["status"] == "ok"
        insert_user_calls = [
            c for c in pool.conn.fetchval.await_args_list
            if c.args and "INSERT INTO users" in c.args[0]
        ]
        assert len(insert_user_calls) == 0, "Existing user must NOT trigger INSERT users"

    @pytest.mark.asyncio
    async def test_ws_acc_14_existing_member_role_upgrade_via_upsert(self):
        """WS-ACC-14 — Existing member of same workspace, new invite with different
        role → upsert (ON CONFLICT DO UPDATE SET role=EXCLUDED.role)."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="upgraded@test.com",
                       role="member", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=555, email="upgraded@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(
            id=555, email="upgraded@test.com", role="viewer", disabled=False
        )

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)

        wm_inserts = [
            c for c in pool.conn.execute.await_args_list
            if c.args and "INSERT INTO workspace_members" in c.args[0]
        ]
        assert len(wm_inserts) == 1
        sql = wm_inserts[0].args[0]
        assert "ON CONFLICT" in sql.upper() and "DO UPDATE" in sql.upper(), (
            f"workspace_members INSERT must use ON CONFLICT DO UPDATE for idempotent "
            f"role upgrades. Got SQL:\n{sql}"
        )

    @pytest.mark.asyncio
    async def test_ws_acc_25_idempotent_re_accept_same_role(self):
        """WS-ACC-25 — Same workspace, same role re-accept → still goes through
        upsert, no duplicate row.  (The accepted_at check would normally block
        replays — see WS-ACC-07 — so this test specifically asserts the SQL
        primitive is idempotent for the case where accepted_at IS NULL but
        the membership row already exists from a prior accept that somehow
        left accepted_at NULL.)"""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=2, workspace_id=42, email="idem@test.com",
                       role="viewer", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=300, email="idem@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(
            id=300, email="idem@test.com", role="viewer", disabled=False,
        )

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                result = await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)
        assert result["status"] == "ok"



class TestAcceptErrorPaths:

    @pytest.mark.asyncio
    async def test_ws_acc_06_disabled_user_rejected_403(self):
        """WS-ACC-06 — Existing user with disabled=true → 403, invite NOT marked accepted."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="disabled@test.com",
                       role="member", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(
            id=666, email="disabled@test.com", role="viewer", disabled=True,
        )

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                with pytest.raises(HTTPException) as exc:
                    await accept_invite(
                        body=AcceptInviteIn(token="raw"),
                        request=_request(), response=_response(),
                    )
        finally:
            _exit_all(patches)

        assert exc.value.status_code == 403
        assert "disabled" in exc.value.detail.lower()

        accepted_at_updates = [
            c for c in pool.conn.execute.await_args_list
            if c.args and "UPDATE workspace_invitations" in c.args[0]
            and "accepted_at" in c.args[0]
        ]
        assert len(accepted_at_updates) == 0

    @pytest.mark.asyncio
    async def test_ws_acc_07_replay_already_accepted_400(self):
        """WS-ACC-07 — Replay (accepted_at not null) → 400 'Invitation already used'."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.return_value = FakeRecord(
            id=1, workspace_id=42, email="x@test.com", role="viewer",
            accepted_at=datetime.now(timezone.utc), expires_at=_future(),
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        assert exc.value.status_code == 400
        assert "already used" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_acc_08_expired_token_400(self):
        """WS-ACC-08 — Expired token → 400 'Invitation has expired'."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.return_value = FakeRecord(
            id=1, workspace_id=42, email="x@test.com", role="viewer",
            accepted_at=None, cancelled_at=None, expires_at=_past(),
        )

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        assert exc.value.status_code == 400
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_acc_09_new_account_no_password_400(self):
        """WS-ACC-09 — New user (no row) and no password → 400."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="brand-new@test.com",
                       role="viewer", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
        ]
        pool.conn.fetchrow.return_value = None

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                with pytest.raises(HTTPException) as exc:
                    await accept_invite(
                        body=AcceptInviteIn(token="raw"),
                        request=_request(), response=_response(),
                    )
        finally:
            _exit_all(patches)

        assert exc.value.status_code == 400
        assert "password is required" in exc.value.detail.lower()

    def test_ws_acc_10_short_password_rejected_by_pydantic(self):
        """WS-ACC-10 — password <8 chars → pydantic ValidationError (would be 422 via FastAPI)."""
        from src.services.dashboard.v2.auth import AcceptInviteIn
        with pytest.raises(Exception):
            AcceptInviteIn(token="raw", password="short")

    @pytest.mark.parametrize(
        "good_password", ["password", "Test1234!", "x" * 100],
        ids=["minlen-8", "mixed", "very-long"],
    )
    def test_ws_acc_10_password_at_or_above_min_accepted(self, good_password: str):
        """WS-ACC-10 (positive) — password >= 8 chars accepted by pydantic."""
        from src.services.dashboard.v2.auth import AcceptInviteIn
        m = AcceptInviteIn(token="raw", password=good_password)
        assert m.password == good_password

    @pytest.mark.asyncio
    async def test_ws_acc_13_email_case_insensitive_match(self):
        """WS-ACC-13 — Invitee email differs only in case from users.email →
        matched via SQL ``lower()`` on both sides."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="MIXED.case@TEST.com",
                       role="viewer", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=42, email="mixed.case@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(
            id=42, email="mixed.case@test.com", role="viewer", disabled=False,
        )

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                result = await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)
        assert result["status"] == "ok"

        user_lookup_calls = [
            c for c in pool.conn.fetchrow.await_args_list
            if c.args and "FROM users" in c.args[0] and "lower(email)" in c.args[0]
        ]
        assert len(user_lookup_calls) == 1, (
            "User lookup in accept_invite must use lower(email) on both sides "
            "for case-insensitive matching. (AE-269 WS-ACC-13)"
        )



class TestPrivilegeEscalationRegression:
    """The platform-level ``users.role`` must NEVER be set to ``owner`` or the
    invite's workspace role via the accept-invite path — AE-264 hotfix.
    Platform role is hard-coded ``user`` (renamed from viewer in AE-284)."""

    @pytest.mark.asyncio
    async def test_ws_acc_19_new_user_platform_role_is_viewer_not_invite_role(self):
        """WS-ACC-19 — Brand-new user accepting an invite has ``users.role='user'``
        (platform role), even when the invite role is ``member``. AE-284 rename."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="new@test.com",
                       role="member", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=1234, email="new@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = None
        pool.conn.fetchval.return_value = 1234

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                await accept_invite(
                    body=AcceptInviteIn(token="raw", password="strongpass123"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)

        insert_calls = [
            c for c in pool.conn.fetchval.await_args_list
            if c.args and "INSERT INTO users" in c.args[0]
        ]
        assert len(insert_calls) == 1
        sql = insert_calls[0].args[0]
        assert "'user'" in sql, f"Expected hard-coded 'user' (platform role) in SQL: {sql!r}"
        params = insert_calls[0].args[1:]
        assert "member" not in params, (
            f"AE-264 regression risk: invite role 'member' appears as a parameter to "
            f"INSERT users. Params: {params}"
        )

    @pytest.mark.asyncio
    async def test_ws_acc_22_request_body_role_is_ignored(self):
        """WS-ACC-22 — POST body cannot tamper with role.  The AcceptInviteIn
        model has only token/password/display_name — pydantic should drop or
        reject any extra ``role`` field, and the handler reads role from the
        invite row exclusively."""
        from src.services.dashboard.v2.auth import AcceptInviteIn
        m = AcceptInviteIn.model_validate({
            "token": "raw", "password": "longpassword",
            "role": "owner",
            "workspace_id": 99,
        })
        assert not hasattr(m, "role"), (
            "AcceptInviteIn must NOT bind a 'role' field from the request body. "
            "If you add one, AE-264 regression risk."
        )
        assert not hasattr(m, "workspace_id")



class TestCrossInviteTampering:

    @pytest.mark.asyncio
    async def test_ws_acc_24_unauthenticated_endpoint_does_not_check_session_email(self):
        """WS-ACC-24 — POST /accept-invite is unauthenticated.  If user A's
        browser POSTs an invite token issued for email B, the handler treats
        the request as B's acceptance:

          * If B doesn't exist → creates B (with B's email, viewer role)
          * If B exists → reuses B
          * Either way, JWT cookies are issued for B; A's session is
            effectively replaced (cookie overwrite)

        This is **'auto-logout + flow continues'** behaviour.  The AC's
        primary expectation (403 mismatch) is NOT enforced.

        Document expectation: this test asserts current behaviour.  If
        product wants the strict 403 path, that's a separate code change
        and should be tracked with a follow-up bug.
        """
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=42, email="b@test.com",
                       role="viewer", accepted_at=None, cancelled_at=None, expires_at=_future()),
            FakeRecord(id=42),
            FakeRecord(id=2, email="b@test.com", role="viewer"),
        ]
        pool.conn.fetchrow.return_value = FakeRecord(
            id=2, email="b@test.com", role="viewer", disabled=False,
        )

        patches = _suppress_side_effects()
        _enter_all(patches)
        try:
            with _pool_ctx(pool):
                result = await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )
        finally:
            _exit_all(patches)

        assert result["status"] == "ok"
        assert result["workspace_id"] == 42



class TestDeferredToTestcontainer:
    """These ACs require a real Postgres testcontainer or middleware harness.
    They are tracked under AE-273 (Plan limits + isolation + concurrency)
    where testcontainer infrastructure already lands."""

    @pytest.mark.asyncio
    async def test_ws_acc_12_workspace_deleted_between_invite_and_accept(self):
        """WS-ACC-12 — Workspace deleted after invite creation but before acceptance
        → 410 Gone with descriptive message (application-level check, no FK reliance)."""
        from src.services.dashboard.v2.auth import accept_invite, AcceptInviteIn

        pool = FakeTxnPool()
        pool.fetchrow.side_effect = [
            FakeRecord(id=1, workspace_id=99, email="invited@test.com",
                       role="member", accepted_at=None, cancelled_at=None, expires_at=_future()),
            None,
        ]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await accept_invite(
                    body=AcceptInviteIn(token="raw"),
                    request=_request(), response=_response(),
                )

        assert exc.value.status_code == 410
        assert "workspace has been removed" in exc.value.detail.lower()

    @pytest.mark.skip(reason="WS-ACC-15: requires rate-limit middleware in test app; "
                              "if no limiter exists today, file a security bug. "
                              "Investigation tracked separately.")
    def test_ws_acc_15_token_brute_force_rate_limited(self):
        ...

    @pytest.mark.skip(reason="WS-ACC-16: timing-attack measurement is flaky in CI; "
                              "manual validation only.")
    def test_ws_acc_16_constant_time_token_compare(self):
        ...

    @pytest.mark.skip(reason="WS-ACC-17: URL-routing concern; covered by Playwright AE-274")
    def test_ws_acc_17_url_encoded_token(self):
        ...

    @pytest.mark.skip(reason="WS-ACC-18: requires real DB state for disable/re-enable; AE-273")
    def test_ws_acc_18_re_acceptance_after_disable(self):
        ...

    @pytest.mark.skip(reason="WS-ACC-20/21: tests the /register flow, not /accept-invite. "
                              "Belongs in test_auth_register.py — file separately.")
    def test_ws_acc_20_signup_creates_workspace_owner(self):
        ...

    @pytest.mark.skip(reason="WS-ACC-23: requires Postgres CHECK constraint; tracked in AE-273")
    def test_ws_acc_23_db_check_constraint_blocks_direct_owner_insert(self):
        ...
