"""Permission grid tests for the workspace section.

Covers Story AE-267 (parent epic AE-266 / AE-7).

For every (role, endpoint) combination where the role is **not** allowed,
assert exactly ``HTTPException(403, "Permission denied: <perm>")``.
Positive sanity: each role can hit the endpoints it *is* allowed to.

Test strategy
-------------
The permission gate lives in the FastAPI dependency
``require_permission(name)`` from ``src.services.dashboard.v2._deps``.  We
exercise the dependency's inner ``_checker`` coroutine directly, with the
underlying ``get_permissions_for_role`` patched to return the canonical
role→permission matrix from
``scripts/migrations/202605300001_consolidate_roles_to_three.sql`` and
``scripts/migrations/202605220001_named_permissions.sql``.

This isolates the RBAC enforcement from DB / network and keeps the suite
fast.  The full HTTP wiring (route → dep → handler) is exercised by the
adjacent ``test_workspace_v2.py`` and the e2e Playwright spec from AE-274.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.services.dashboard.v2._deps import Principal, require_permission

_PERMS_MODULE = "src.services.dashboard.v2._permissions.get_permissions_for_role"



ALL_PERMISSIONS = frozenset({
    "workspace.view",
    "workspace.settings.view",
    "workspace.settings.edit",
    "workspace.billing.view",
    "workspace.billing.manage",
    "workspace.members.view",
    "workspace.members.invite",
    "workspace.members.remove",
    "workspace.members.role.change",
    "workspace.ownership.transfer",
    "workspace.integrations.view",
    "workspace.integrations.manage",
    "workspace.audit_log.view",
    "channel.view",
    "channel.create",
    "channel.settings.edit",
    "channel.delete",
    "channel.credentials.view.labels",
    "channel.credentials.manage",
    "project.view",
    "project.create",
    "project.edit",
    "project.delete",
    "project.approve",
    "project.publish",
    "job.view",
    "job.trigger",
    "job.cancel",
    "job.retry",
    "analytics.view",
    "analytics.export",
    "credentials.view.labels",
    "credentials.view.manage",
})

OWNER_PERMS = ALL_PERMISSIONS

MEMBER_PERMS = frozenset({
    "workspace.view",
    "workspace.settings.view",
    "workspace.members.view",
    "workspace.integrations.view",
    "channel.view",
    "channel.create",
    "channel.settings.edit",
    "channel.delete",
    "channel.credentials.view.labels",
    "channel.credentials.manage",
    "project.view",
    "project.create",
    "project.edit",
    "project.delete",
    "project.approve",
    "project.publish",
    "job.view",
    "job.trigger",
    "job.cancel",
    "job.retry",
    "analytics.view",
    "analytics.export",
    "credentials.view.labels",
    "credentials.view.manage",
})

VIEWER_PERMS = frozenset({
    "workspace.view",
    "channel.view",
    "project.view",
    "job.view",
    "analytics.view",
})

ROLE_MATRIX: dict[str, frozenset[str]] = {
    "owner": OWNER_PERMS,
    "member": MEMBER_PERMS,
    "viewer": VIEWER_PERMS,
}



def _make_principal(role: str, *, workspace_id: int = 1, user_id: int = 42) -> Principal:
    return Principal(
        user_id=user_id,
        email=f"{role}@test.com",
        role=role,
        source="v2_jwt",
        workspace_id=workspace_id,
    )


def _patch_perms(role: str):
    """Patch ``get_permissions_for_role`` to return the canonical set for *role*."""
    return patch(
        _PERMS_MODULE,
        new_callable=AsyncMock,
        return_value=ROLE_MATRIX[role],
    )


async def _assert_denied(permission: str, role: str) -> None:
    """Calling require_permission(*) with *role* must raise 403 with the right detail."""
    checker = require_permission(permission)
    principal = _make_principal(role=role)
    with _patch_perms(role):
        with pytest.raises(HTTPException) as exc_info:
            await checker(principal)
    assert exc_info.value.status_code == 403, (
        f"Expected 403 for role={role!r} permission={permission!r}, "
        f"got {exc_info.value.status_code}"
    )
    assert f"Permission denied: {permission}" in exc_info.value.detail, (
        f"Expected detail to mention permission name; got {exc_info.value.detail!r}"
    )


async def _assert_allowed(permission: str, role: str) -> None:
    """Calling require_permission(*) with an allowed *role* must return the Principal."""
    checker = require_permission(permission)
    principal = _make_principal(role=role)
    with _patch_perms(role):
        result = await checker(principal)
    assert result is principal, "require_permission should return the principal on success"



class TestRoleMatrixSnapshot:
    """Lock the role-permission matrix.  Update both this file AND the
    migration if the matrix legitimately changes."""

    def test_owner_has_all_permissions(self):
        assert OWNER_PERMS == ALL_PERMISSIONS
        assert len(OWNER_PERMS) == 33

    def test_member_has_24_permissions_no_people_management(self):
        assert len(MEMBER_PERMS) == 24
        forbidden_for_member = {
            "workspace.settings.edit",
            "workspace.billing.view",
            "workspace.billing.manage",
            "workspace.members.invite",
            "workspace.members.remove",
            "workspace.members.role.change",
            "workspace.ownership.transfer",
            "workspace.integrations.manage",
            "workspace.audit_log.view",
        }
        assert forbidden_for_member.isdisjoint(MEMBER_PERMS), (
            f"Member must not have any of {forbidden_for_member}; "
            f"overlap: {forbidden_for_member & MEMBER_PERMS}"
        )

    def test_viewer_has_only_5_read_permissions(self):
        assert len(VIEWER_PERMS) == 5
        assert all(p.endswith(".view") for p in VIEWER_PERMS), (
            f"Viewer must be read-only; non-view perms: "
            f"{[p for p in VIEWER_PERMS if not p.endswith('.view')]}"
        )

    def test_viewer_perms_are_subset_of_member_perms(self):
        assert VIEWER_PERMS.issubset(MEMBER_PERMS)

    def test_member_perms_are_subset_of_owner_perms(self):
        assert MEMBER_PERMS.issubset(OWNER_PERMS)



class TestPermissionGridNegative:
    """For every blocked (role, endpoint) pair, require_permission must
    raise HTTPException(403, "Permission denied: <perm>")."""

    @pytest.mark.asyncio
    async def test_ws_perm_01_member_cannot_rename_workspace(self):
        """WS-PERM-01 — Member cannot PUT /workspace (workspace.settings.edit)."""
        await _assert_denied("workspace.settings.edit", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_02_viewer_cannot_rename_workspace(self):
        """WS-PERM-02 — Viewer cannot PUT /workspace."""
        await _assert_denied("workspace.settings.edit", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_03_member_cannot_create_invite(self):
        """WS-PERM-03 — Member cannot POST /workspace/invites
        (workspace.members.invite)."""
        await _assert_denied("workspace.members.invite", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_04_viewer_cannot_create_invite(self):
        """WS-PERM-04 — Viewer cannot POST /workspace/invites."""
        await _assert_denied("workspace.members.invite", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_05_member_cannot_revoke_invite(self):
        """WS-PERM-05 — Member cannot DELETE /workspace/invites/{id}
        (same workspace.members.invite gate)."""
        await _assert_denied("workspace.members.invite", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_06_member_cannot_change_member_role(self):
        """WS-PERM-06 — Member cannot PUT /workspace/members/{id}/role
        (workspace.members.role.change)."""
        await _assert_denied("workspace.members.role.change", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_07_viewer_cannot_change_member_role(self):
        """WS-PERM-07 — Viewer cannot PUT /workspace/members/{id}/role."""
        await _assert_denied("workspace.members.role.change", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_08_member_cannot_remove_member(self):
        """WS-PERM-08 — Member cannot DELETE /workspace/members/{id}
        (workspace.members.remove)."""
        await _assert_denied("workspace.members.remove", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_09_viewer_cannot_remove_member(self):
        """WS-PERM-09 — Viewer cannot DELETE /workspace/members/{id}."""
        await _assert_denied("workspace.members.remove", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_10_member_cannot_transfer_ownership(self):
        """WS-PERM-10 — Member cannot POST /workspace/transfer-ownership
        (workspace.ownership.transfer)."""
        await _assert_denied("workspace.ownership.transfer", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_11_viewer_cannot_transfer_ownership(self):
        """WS-PERM-11 — Viewer cannot POST /workspace/transfer-ownership."""
        await _assert_denied("workspace.ownership.transfer", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_12_member_cannot_manage_integrations(self):
        """WS-PERM-12 — Member cannot PUT /workspace/integrations
        (workspace.integrations.manage)."""
        await _assert_denied("workspace.integrations.manage", "member")

    @pytest.mark.asyncio
    async def test_ws_perm_13_viewer_cannot_view_integrations(self):
        """WS-PERM-13 — Viewer cannot GET /workspace/integrations
        (workspace.integrations.view — viewer has no .view perm for this)."""
        await _assert_denied("workspace.integrations.view", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_14_viewer_cannot_edit_settings(self):
        """WS-PERM-14 — Viewer cannot PUT /workspace/settings
        (workspace.settings.edit)."""
        await _assert_denied("workspace.settings.edit", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_15_viewer_cannot_create_brand(self):
        """WS-PERM-15 — Viewer cannot POST /workspace/brands (channel.create)."""
        await _assert_denied("channel.create", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_16_viewer_cannot_create_project(self):
        """WS-PERM-16 — Viewer cannot POST /workspace/projects (project.create)."""
        await _assert_denied("project.create", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_17_viewer_cannot_approve_project(self):
        """WS-PERM-17 — Viewer cannot approve a project (project.approve)."""
        await _assert_denied("project.approve", "viewer")

    @pytest.mark.asyncio
    async def test_ws_perm_18_member_cannot_view_audit_log(self):
        """WS-PERM-18 — Member cannot GET workspace audit log
        (workspace.audit_log.view — owner-only)."""
        await _assert_denied("workspace.audit_log.view", "member")



class TestPermissionGridPositive:
    """Mirror of the negative grid — assert each role *can* call what it
    is supposed to.  Catches over-restrictive regressions."""

    @pytest.mark.parametrize("permission", sorted(OWNER_PERMS))
    @pytest.mark.asyncio
    async def test_owner_has_every_permission(self, permission: str):
        await _assert_allowed(permission, "owner")

    @pytest.mark.parametrize(
        "permission",
        ["workspace.view", "workspace.members.view", "workspace.integrations.view",
         "channel.create", "project.create", "project.edit", "project.approve",
         "job.trigger", "analytics.view"],
    )
    @pytest.mark.asyncio
    async def test_member_can_use_content_and_pipeline_perms(self, permission: str):
        await _assert_allowed(permission, "member")

    @pytest.mark.parametrize(
        "permission",
        ["workspace.view", "channel.view", "project.view", "job.view", "analytics.view"],
    )
    @pytest.mark.asyncio
    async def test_viewer_can_read_view_endpoints(self, permission: str):
        await _assert_allowed(permission, "viewer")



class TestPermissionDenialContract:
    """The 403 ``detail`` string is a stable contract: clients (and Sentry
    alert rules) match on the literal prefix."""

    @pytest.mark.asyncio
    async def test_403_detail_contains_literal_prefix(self):
        checker = require_permission("workspace.members.invite")
        principal = _make_principal(role="member")
        with _patch_perms("member"):
            with pytest.raises(HTTPException) as exc_info:
                await checker(principal)
        assert exc_info.value.detail.startswith("Permission denied: "), (
            f"Detail prefix changed; FE error handling will break. "
            f"Got: {exc_info.value.detail!r}"
        )
        assert exc_info.value.detail.endswith("workspace.members.invite")

    @pytest.mark.asyncio
    async def test_403_for_unknown_permission_still_denies(self):
        """If a typo'd permission ever makes it past code review, every role
        must be denied (fail-closed)."""
        checker = require_permission("workspace.does.not.exist")
        for role in ("owner", "member", "viewer"):
            principal = _make_principal(role=role)
            with _patch_perms(role):
                with pytest.raises(HTTPException) as exc_info:
                    await checker(principal)
            assert exc_info.value.status_code == 403, (
                f"Unknown perm must fail-closed for role={role}, "
                f"got {exc_info.value.status_code}"
            )
