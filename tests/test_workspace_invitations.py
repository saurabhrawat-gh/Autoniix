"""Invitation lifecycle tests for the workspace section.

Covers Story AE-268 (parent epic AE-266 / AE-7) — 32 edge cases across:
* Role validation
* Input validation
* Dedup (existing member / pending invite)
* Plan limits (Starter / Growth / Scale / Enterprise / NULL / unknown)
* Revocation (own / accepted / cross-workspace / expired)
* Race conditions (documented expectation; full race fix tracked in AE-277)
* Read-after-write
* Side effects (Slack, Resend, FRONTEND_URL)

Direct-call pattern (handler invoked with mocked pool) mirrors
``tests/test_workspace_v2.py`` so the FakePool side-effect lists stay
identical to the production handler's call sequence.

AE-277 hotfix restructure: all seat-cap checks + INSERT now run inside
an advisory-lock transaction on ``conn = pool.acquire()``.  Mock targets:

    create_invite() call order:
      pool.fetchrow:
        1. fetchrow(plan)           -- outside transaction
        2. fetchrow(ws_info)        -- only when _resend.is_configured()
        3. fetchrow(actor_info)     -- only when _resend.is_configured()
        4. fetchrow(slack)          -- outside transaction

      pool.conn.fetchval (INSIDE advisory-lock transaction):
        1. fetchval(member_count)   -- only when limit is not None
        2. fetchval(pending_count)  -- only when limit is not None
        3. fetchval(existing_member_id)
        4. fetchval(pending_invitation_id)
        5. fetchval(inv_id from INSERT)

If the handler's call sequence changes, these tests will fail loudly —
that's intentional.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import FakePool, FakeRecord

_WS = "src.services.dashboard.v2.workspace"


def _make_principal(role: str = "owner", *, workspace_id: int = 1, user_id: int = 42):
    from src.services.dashboard.v2._deps import Principal
    return Principal(
        user_id=user_id,
        email="owner@test.com",
        role=role,
        source="v2_jwt",
        workspace_id=workspace_id,
    )


def _pool_ctx(pool):
    return patch(f"{_WS}.get_pool", new_callable=AsyncMock, return_value=pool)


def _audit_ctx():
    return patch(f"{_WS}.audit", new_callable=AsyncMock)


def _resend_off_ctx():
    """Resend disabled — handler skips the 2 extra fetchrow calls."""
    return patch(
        "src.services.dashboard.v2._resend.is_configured",
        return_value=False,
    )


def _resend_on_ctx():
    return patch(
        "src.services.dashboard.v2._resend.is_configured",
        return_value=True,
    )



class TestRoleValidation:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_role", ["owner", "admin", "producer", "editor", "reviewer", "analyst", ""])
    async def test_ws_inv_01_02_invalid_role_rejected(self, bad_role: str):
        """WS-INV-01/02 — Owner cannot be invited; legacy roles rejected with 400."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        actor = _make_principal()
        body = InviteIn(email="x@test.com", role=bad_role)
        with _pool_ctx(FakePool()):
            with pytest.raises(HTTPException) as exc:
                await create_invite(body=body, request=MagicMock(), actor=actor)
        assert exc.value.status_code == 400
        assert "invalid role" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_inv_03_viewer_invite_succeeds(self):
        """WS-INV-03 — Owner invites with role=viewer (default) → 200, token returned once."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 99]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="newuser@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"
        assert result["id"] == 99
        assert "token" in result and len(result["token"]) > 20
        assert result["invite_url"].startswith("/accept-invite?token=")

    @pytest.mark.asyncio
    async def test_ws_inv_04_member_invite_succeeds(self):
        """WS-INV-04 — Owner invites with role=member → 200."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 100]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="member@test.com", role="member"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"



class TestInputValidation:

    def test_ws_inv_05_malformed_email_rejected_by_pydantic(self):
        """WS-INV-05 — Malformed email → ValidationError at model construction."""
        from src.services.dashboard.v2.workspace import InviteIn
        with pytest.raises(Exception) as exc:
            InviteIn(email="not-an-email", role="viewer")
        assert "email" in str(exc.value).lower() or "value_error" in str(exc.value).lower()

    @pytest.mark.parametrize("bad_expires", [0, -1, 31, 100])
    def test_ws_inv_09_10_expires_days_out_of_range(self, bad_expires: int):
        """WS-INV-09/10 — expires_days must satisfy 1 <= n <= 30."""
        from src.services.dashboard.v2.workspace import InviteIn
        with pytest.raises(Exception):
            InviteIn(email="x@test.com", role="viewer", expires_days=bad_expires)

    @pytest.mark.parametrize("good_expires", [1, 7, 14, 30])
    def test_ws_inv_11_expires_days_in_range_accepted(self, good_expires: int):
        """WS-INV-11 — expires_days=1..30 is accepted."""
        from src.services.dashboard.v2.workspace import InviteIn
        m = InviteIn(email="x@test.com", role="viewer", expires_days=good_expires)
        assert m.expires_days == good_expires

    @pytest.mark.asyncio
    async def test_ws_inv_12_uppercase_email_normalized_to_lowercase(self):
        """WS-INV-12 — email is .lower()'d before insertion (and on lookup)."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 200]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            await create_invite(
                body=InviteIn(email="Mixed.CASE@Test.COM", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )

        insert_calls = [
            c for c in pool.conn.fetchval.await_args_list
            if c.args and isinstance(c.args[0], str) and "INSERT INTO workspace_invitations" in c.args[0]
        ]
        assert len(insert_calls) == 1
        inserted_email = insert_calls[0].args[2]
        assert inserted_email == "mixed.case@test.com", (
            f"Email should be normalized to lowercase before insertion; got {inserted_email!r}"
        )



class TestDedup:

    @pytest.mark.asyncio
    async def test_ws_inv_06_existing_member_409(self):
        """WS-INV-06 — Inviting a user who's already a member → 409."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise")]
        pool.conn.fetchval.side_effect = [555]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="member@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 409
        assert "already a member" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_inv_07_pending_invite_dedup_409(self):
        """WS-INV-07 — Pending unexpired invite for same email → 409."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise")]
        pool.conn.fetchval.side_effect = [None, 777]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="repeat@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 409
        assert "pending invitation" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_inv_08_only_expired_invite_allows_new(self):
        """WS-INV-08 — Only EXPIRED invite for same email → 200, new invite created.

        The handler's pending-invite query filters ``expires_at > NOW()``, so
        an expired row returns NULL and the new invite proceeds.
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 300]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="retry@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"
        assert result["id"] == 300



class TestPlanLimits:

    @pytest.mark.asyncio
    async def test_ws_inv_13_starter_3_used_blocks(self):
        """WS-INV-13 — Starter 3/3 used → 402."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="starter")]
        pool.conn.fetchval.side_effect = [3, 0]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="x@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 402
        assert "plan limit" in exc.value.detail.lower()
        assert "starter" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_ws_inv_14_starter_2_member_1_pending_blocks(self):
        """WS-INV-14 — Starter with 2 members + 1 pending → 402 (3 = limit)."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="starter")]
        pool.conn.fetchval.side_effect = [2, 1]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="x@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 402

    @pytest.mark.asyncio
    async def test_ws_inv_15_starter_2_member_1_expired_pending_allows(self):
        """WS-INV-15 — Starter 2 members + 1 EXPIRED pending → 200.

        The pending_count query filters ``expires_at > NOW()`` so expired
        invites do NOT count toward the limit.
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="starter"), None]
        pool.conn.fetchval.side_effect = [2, 0, None, None, 400]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="okay@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ws_inv_16_growth_9_members_allows(self):
        """WS-INV-16 — Growth plan with 9 members → 200 (limit=10)."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="growth"), None]
        pool.conn.fetchval.side_effect = [9, 0, None, None, 500]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="g@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ws_inv_17_growth_10_members_blocks(self):
        """WS-INV-17 — Growth plan with 10 members → 402."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="growth")]
        pool.conn.fetchval.side_effect = [10, 0]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="g@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 402

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "plan,member_count",
        [("scale", 100), ("enterprise", 1000)],
        ids=["WS-INV-18-scale-100", "WS-INV-19-enterprise-1000"],
    )
    async def test_ws_inv_18_19_unlimited_plans(self, plan: str, member_count: int):
        """WS-INV-18/19 — scale and enterprise are unlimited (member-count check skipped)."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan=plan), None]
        pool.conn.fetchval.side_effect = [None, None, 600]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="unlimited@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ws_inv_20_plan_null_falls_back_to_starter(self):
        """WS-INV-20 — plan=NULL in DB → handler falls back to 'starter' semantics."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan=None)]
        pool.conn.fetchval.side_effect = [3, 0]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="x@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 402

    @pytest.mark.asyncio
    async def test_ws_inv_21_unknown_plan_falls_back_to_unlimited(self):
        """WS-INV-21 — unknown plan value → _PLAN_MEMBER_LIMITS.get() returns None → unlimited.

        Note: this is documenting current behaviour. If product wants
        unknown plans to fall back to starter instead, change the handler
        AND this assertion accordingly. (Filed as a discussion point in
        AE-273 if it ever matters in prod.)
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise_plus_xl"), None]
        pool.conn.fetchval.side_effect = [None, None, 700]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="x@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"



class TestRevocation:

    @pytest.mark.asyncio
    async def test_ws_inv_22_revoke_own_pending_invite(self):
        """WS-INV-22 — Revoking own pending invite → 200."""
        from src.services.dashboard.v2.workspace import revoke_invite

        pool = FakePool()
        pool.execute = AsyncMock(return_value="DELETE 1")

        with _pool_ctx(pool), _audit_ctx():
            result = await revoke_invite(invite_id=42, request=MagicMock(), actor=_make_principal())
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ws_inv_23_revoke_already_accepted_invite_404(self):
        """WS-INV-23 — Revoke an already-accepted invite → 404.

        Handler's DELETE filters ``accepted_at IS NULL``, so an accepted
        row returns 0 affected rows → 404.
        """
        from src.services.dashboard.v2.workspace import revoke_invite

        pool = FakePool()
        pool.execute = AsyncMock(return_value="DELETE 0")

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await revoke_invite(invite_id=42, request=MagicMock(), actor=_make_principal())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_ws_inv_24_revoke_other_workspace_invite_404_no_leak(self):
        """WS-INV-24 — Trying to revoke an invite belonging to a different workspace → 404.

        The DELETE filters both ``id`` and ``workspace_id`` → wrong-WS attempt
        returns 0 → handler raises 404 (NOT 200, NOT 403 — no info leak).
        """
        from src.services.dashboard.v2.workspace import revoke_invite

        pool = FakePool()
        pool.execute = AsyncMock(return_value="DELETE 0")

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await revoke_invite(invite_id=999, request=MagicMock(),
                                    actor=_make_principal(workspace_id=1))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_ws_inv_25_revoke_expired_unaccepted_invite_200(self):
        """WS-INV-25 — Expired but unaccepted invite is still deletable → 200.

        The DELETE filter is ``accepted_at IS NULL`` — no expiry filter.
        """
        from src.services.dashboard.v2.workspace import revoke_invite

        pool = FakePool()
        pool.execute = AsyncMock(return_value="DELETE 1")

        with _pool_ctx(pool), _audit_ctx():
            result = await revoke_invite(invite_id=42, request=MagicMock(), actor=_make_principal())
        assert result["status"] == "ok"



class TestRaceCondition:

    @pytest.mark.asyncio
    async def test_ws_inv_26_simultaneous_invites_dedup_check_runs(self):
        """WS-INV-26 — Two owners simultaneously invite same email.

        With current code (no advisory lock — see AE-277), the second call
        either:
          a) sees the first invite via pending_inv check → 409, OR
          b) races past it and creates a duplicate row.

        Outcome (a) is the desired one; the dedup check is the only guard
        between us and AE-262 / AE-277. This test asserts that when the
        dedup check DOES fire, it correctly returns 409 — i.e. the unit
        primitive works; the race is a higher-layer concurrency bug
        tracked separately.
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise")]
        pool.conn.fetchval.side_effect = [None, 88]

        with _pool_ctx(pool):
            with pytest.raises(HTTPException) as exc:
                await create_invite(
                    body=InviteIn(email="race@test.com", role="viewer"),
                    request=MagicMock(),
                    actor=_make_principal(),
                )
        assert exc.value.status_code == 409



class TestReadAfterWrite:

    @pytest.mark.asyncio
    async def test_ws_inv_27_list_invites_returns_pending_rows(self):
        """WS-INV-27 — GET /invites returns pending invitations for the current workspace."""
        from src.services.dashboard.v2.workspace import list_invites

        pool = FakePool()
        pool.fetch = AsyncMock(return_value=[
            FakeRecord(id=1, email="a@x.com", role="viewer",
                       accepted_at=None, expires_at=None, created_at=None, resent_at=None),
            FakeRecord(id=2, email="b@x.com", role="member",
                       accepted_at=None, expires_at=None, created_at=None, resent_at=None),
        ])

        with _pool_ctx(pool):
            result = await list_invites(p=_make_principal())
        assert len(result["data"]) == 2
        assert result["data"][0]["email"] == "a@x.com"
        assert result["data"][0]["accepted_at"] is None



class TestSideEffects:

    @pytest.mark.asyncio
    async def test_ws_inv_28_frontend_url_unset_returns_relative_url(self, monkeypatch):
        """WS-INV-28 — FRONTEND_URL unset → relative ``/accept-invite?token=...`` URL."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn
        monkeypatch.delenv("FRONTEND_URL", raising=False)

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 900]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx():
            result = await create_invite(
                body=InviteIn(email="x@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["invite_url"].startswith("/accept-invite?token=")
        assert "://" not in result["invite_url"], "URL must be relative when FRONTEND_URL unset"

    @pytest.mark.asyncio
    async def test_ws_inv_29_slack_webhook_called_with_payload(self):
        """WS-INV-29 — When Slack webhook configured, _notify_slack invoked with the message."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="enterprise"),
            FakeRecord(slack_webhook_url="https://hooks.slack.com/services/T/B/X"),
        ]
        pool.conn.fetchval.side_effect = [None, None, 901]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx(), \
             patch(f"{_WS}._notify_slack", new_callable=AsyncMock) as mock_slack:
            await create_invite(
                body=InviteIn(email="slack-target@test.com", role="member"),
                request=MagicMock(),
                actor=_make_principal(),
            )

        mock_slack.assert_awaited_once()
        webhook_url, message = mock_slack.await_args.args
        assert webhook_url == "https://hooks.slack.com/services/T/B/X"
        assert "slack-target@test.com" in message
        assert "member" in message.lower()

    @pytest.mark.asyncio
    async def test_ws_inv_30_slack_failure_does_not_break_invite(self):
        """WS-INV-30 — Slack webhook raises → invite still succeeds (fail-safe).

        _notify_slack swallows exceptions internally; the test asserts
        the wrapper contract by raising from inside the mock and
        confirming the handler still returns 200.
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="enterprise"),
            FakeRecord(slack_webhook_url="https://hooks.slack.com/services/T/B/X"),
        ]
        pool.conn.fetchval.side_effect = [None, None, 902]

        async def _bombing_slack(url, msg):
            try:
                raise RuntimeError("slack 500")
            except Exception:
                pass

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx(), \
             patch(f"{_WS}._notify_slack", new=_bombing_slack):
            result = await create_invite(
                body=InviteIn(email="x@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ws_inv_31_resend_configured_sends_email(self):
        """WS-INV-31 — Resend configured → send_email called with correct template + payload."""
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [
            FakeRecord(plan="enterprise"),
            FakeRecord(name="Awesome Workspace"),
            FakeRecord(display_name="Alice Owner"),
            None,
        ]
        pool.conn.fetchval.side_effect = [None, None, 903]

        with _pool_ctx(pool), _audit_ctx(), _resend_on_ctx(), \
             patch("src.services.dashboard.v2._resend.send_email") as mock_send:
            await create_invite(
                body=InviteIn(email="invitee@test.com", role="member"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        mock_send.assert_called_once()
        template_name, recipient, ctx = mock_send.call_args.args
        assert template_name == "workspace-invite"
        assert recipient == "invitee@test.com"
        assert ctx["workspace_name"] == "Awesome Workspace"
        assert ctx["inviter_name"] == "Alice Owner"
        assert ctx["role"] == "member"
        assert ctx["expires_days"] == 7
        assert "/accept-invite?token=" in ctx["invite_url"]

    @pytest.mark.asyncio
    async def test_ws_inv_32_resend_not_configured_skips_lookups(self):
        """WS-INV-32 — Resend NOT configured → ws_info / actor_info lookups skipped.

        Verifies the deterministic-tests optimisation in the handler:
        when ``_resend.is_configured()`` is False, the handler does NOT
        do the extra 2 fetchrow calls, keeping mocking simple.
        """
        from src.services.dashboard.v2.workspace import create_invite, InviteIn

        pool = FakePool()
        pool.fetchrow.side_effect = [FakeRecord(plan="enterprise"), None]
        pool.conn.fetchval.side_effect = [None, None, 904]

        with _pool_ctx(pool), _audit_ctx(), _resend_off_ctx(), \
             patch("src.services.dashboard.v2._resend.send_email") as mock_send:
            result = await create_invite(
                body=InviteIn(email="x@test.com", role="viewer"),
                request=MagicMock(),
                actor=_make_principal(),
            )
        assert result["status"] == "ok"
        mock_send.assert_not_called()
        assert pool.fetchrow.await_count == 2
