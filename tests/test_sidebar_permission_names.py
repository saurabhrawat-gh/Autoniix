"""Regression test for AE-214 (#238).

Asserts every `permission: '...'` string referenced by the dashboard
sidebar (`dashboard/src/lib/components/Sidebar.tsx`) exists in the
seeded permissions catalog migration
(`scripts/migrations/202605220001_named_permissions.sql`).

Prevents the FE/BE drift where `Sidebar.tsx` requested permissions
named `content.view` and `provider.view` that the backend never seeded,
causing nav items to be invisible for every role including Owner.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SIDEBAR_PATH = REPO_ROOT / "frontend" / "dashboard" / "src" / "lib" / "components" / "Sidebar.tsx"
PERMS_MIGRATION = REPO_ROOT / "infra" / "migrations" / "202605220001_named_permissions.sql"

_SIDEBAR_PERM_RE = re.compile(r"permission:\s*'([a-z][\w.]+)'")
_MIGRATION_PERM_RE = re.compile(r"\(\s*'([a-z][\w.]+)'\s*,\s*'[^']*'\s*\)")


def _read(p: Path) -> str:
    assert p.exists(), f"expected file not found: {p}"
    return p.read_text(encoding="utf-8")


def test_sidebar_permission_names_exist_in_catalog() -> None:
    sidebar_perms = set(_SIDEBAR_PERM_RE.findall(_read(SIDEBAR_PATH)))
    migration_perms = set(_MIGRATION_PERM_RE.findall(_read(PERMS_MIGRATION)))

    assert sidebar_perms, "Sidebar.tsx had zero permission references — regex broke"
    assert migration_perms, "permissions migration had zero matches — regex broke"

    missing = sorted(sidebar_perms - migration_perms)
    assert not missing, (
        "Sidebar.tsx references permission names that are NOT in the seeded "
        "RBAC catalog. Either add them to "
        "scripts/migrations/202605220001_named_permissions.sql (with a follow-up "
        "migration), or fix the Sidebar string. Missing: " + ", ".join(missing)
    )


@pytest.mark.parametrize(
    "expected",
    [
        "project.view",
        "credentials.view.labels",
        "workspace.view",
        "workspace.members.view",
        "workspace.settings.edit",
    ],
)
def test_sidebar_uses_known_catalog_names(expected: str) -> None:
    """Pin the specific permission names the sidebar must rely on so a future
    refactor that renames them in the catalog also updates Sidebar.tsx."""
    sidebar_perms = set(_SIDEBAR_PERM_RE.findall(_read(SIDEBAR_PATH)))
    assert expected in sidebar_perms, (
        f"Sidebar.tsx no longer references '{expected}'. If this was an "
        "intentional product decision, update this test. Otherwise, restore the "
        "permission gate."
    )
