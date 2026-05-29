"""Regression tests for GET /auth/workspaces (AE-222).

Covers:
- TC-222-01: Legacy seed account whose only workspace is the synthetic
  "Default Workspace" with no onboarding entity_settings row →
  ``onboarding_completed`` MUST be False so the frontend guard redirects to
  the onboarding wizard.
- TC-222-02: Properly onboarded workspace (entity_settings row with
  ``completed: true``) → ``onboarding_completed`` MUST be True.
- TC-222-03: Anonymous principal (no user_id) → returns empty data list
  (no hardcoded fallback — already covered by AE-217 but re-asserted here).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import FakePool, FakeRecord

_AUTH_MODULE = "src.services.dashboard.v2.auth"


def _pool_ctx(pool):
    return patch(f"{_AUTH_MODULE}.get_pool", new_callable=AsyncMock, return_value=pool)


def _principal(user_id: int | None = 1, workspace_id: int = 1, role: str = "owner"):
    from src.services.dashboard.v2._deps import Principal

    return Principal(
        user_id=user_id,
        email="x@y.z",
        role=role,
        source="v2_jwt",
        workspace_id=workspace_id,
    )


# ── TC-222-01: legacy seed account → onboarding_completed = False ───────────


@pytest.mark.asyncio
async def test_list_workspaces_legacy_default_workspace_marks_onboarding_incomplete():
    """The synthetic Default Workspace from init.sql has no onboarding row in
    entity_settings; the LEFT JOIN must yield ``onboarding_completed = False``
    so WorkspaceGuard redirects the user to /onboarding."""
    from src.services.dashboard.v2.auth import list_workspaces

    pool = FakePool()
    pool.fetch = AsyncMock(return_value=[
        FakeRecord(
            id=1,
            name="Default Workspace",
            slug="default",
            plan="starter",
            role="owner",
            active=True,
            onboarding_completed=False,
        )
    ])

    with _pool_ctx(pool):
        result = await list_workspaces(p=_principal())

    assert result == {
        "data": [
            {
                "id": 1,
                "name": "Default Workspace",
                "slug": "default",
                "plan": "starter",
                "role": "owner",
                "active": True,
                "onboarding_completed": False,
            }
        ]
    }
    # Verify the SQL actually LEFT JOINs entity_settings on the onboarding key.
    sql_executed = pool.fetch.call_args[0][0]
    assert "LEFT JOIN entity_settings" in sql_executed
    assert "onboarding" in sql_executed
    assert "onboarding_completed" in sql_executed


# ── TC-222-02: onboarded workspace → onboarding_completed = True ─────────────


@pytest.mark.asyncio
async def test_list_workspaces_onboarded_workspace_marks_onboarding_complete():
    from src.services.dashboard.v2.auth import list_workspaces

    pool = FakePool()
    pool.fetch = AsyncMock(return_value=[
        FakeRecord(
            id=42,
            name="Acme Studios",
            slug="acme-studios",
            plan="growth",
            role="owner",
            active=True,
            onboarding_completed=True,
        )
    ])

    with _pool_ctx(pool):
        result = await list_workspaces(p=_principal())

    assert len(result["data"]) == 1
    assert result["data"][0]["onboarding_completed"] is True
    assert result["data"][0]["name"] == "Acme Studios"


# ── TC-222-03: anonymous principal → empty list (AE-217 guarantee) ───────────


@pytest.mark.asyncio
async def test_list_workspaces_no_user_returns_empty_data():
    """No hardcoded "Default Workspace" fallback for sessions without a
    user_id — must return ``{"data": []}`` exactly."""
    from src.services.dashboard.v2.auth import list_workspaces

    pool = FakePool()
    pool.fetch = AsyncMock(return_value=[])  # never reached

    with _pool_ctx(pool):
        result = await list_workspaces(p=_principal(user_id=None))

    assert result == {"data": []}
    pool.fetch.assert_not_called()
