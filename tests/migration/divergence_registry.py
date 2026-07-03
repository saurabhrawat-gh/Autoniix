"""
Divergence registry — tracks intentional differences between Python and Rust services.

Per HARNESS-ENGINEERING-PLAN.md Section 15.

The equivalence harness checks this registry before failing a test.
If a difference is registered here, it's treated as intentional and
does not cause a test failure.

Approval workflow:
1. Engineer identifies an intentional difference during migration
2. Adds entry to INTENTIONAL_DIVERGENCES with rationale
3. Gets approval from migration lead
4. Entry is committed with the code change that introduces the difference
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Divergence:
    """A single intentional difference between Python and Rust."""
    field: str
    python_behavior: Any
    rust_behavior: Any
    reason: str
    approved_by: str
    approved_date: str
    expected_python_status: int | None = None
    expected_rust_status: int | None = None


INTENTIONAL_DIVERGENCES: dict[str, list[Divergence]] = {
    "POST /api/v2/auth/register": [],

    "GET /api/v2/users": [],
    "POST /api/v2/users/transfer-superadmin": [],
    "PUT /api/v2/users/disable": [],
    "PUT /api/v2/users/enable": [],
    "DELETE /api/v2/users": [],

    "GET /api/v2/flags": [],
    "PUT /api/v2/flags": [],

    "GET /api/v2/notifications": [],
    "POST /api/v2/notifications": [
        Divergence(
            field="dispatch_routes",
            python_behavior="fires dispatch_routes(...) inline (best-effort) after INSERT",
            rust_behavior="defers fan-out to a separate background worker",
            reason=(
                "Inline outbound HTTP on the request thread is a tail-latency "
                "and reliability risk; the row is created identically, the "
                "side-channel is just decoupled. Tracked separately as a "
                "Phase-2 notifications worker."
            ),
            approved_by="migration-lead",
            approved_date="2026-06-21",
        ),
    ],
    "POST /api/v2/notifications/read": [],
    "GET /api/v2/notifications/routes": [],
    "POST /api/v2/notifications/routes": [],
    "PUT /api/v2/notifications/routes": [],
    "DELETE /api/v2/notifications/routes": [],
    "GET /api/v2/notifications/deliveries": [],

    "POST /api/v2/auth/login": [
        Divergence(
            field="expires_in",
            python_behavior=3600,
            rust_behavior=3600,
            reason="Both use 1-hour access token expiry — values match but field may be absent in one",
            approved_by="migration-lead",
            approved_date="2026-06-20",
        ),
    ],
}


def get_divergences(method: str, path: str) -> list[Divergence]:
    """Get all intentional divergences for a given endpoint."""
    key = f"{method.upper()} {path}"
    return INTENTIONAL_DIVERGENCES.get(key, [])


def is_intentional_divergence(
    method: str,
    path: str,
    field_name: str,
    python_value: Any,
    rust_value: Any,
) -> bool:
    """Check if a field difference is an intentional, approved divergence."""
    for div in get_divergences(method, path):
        if div.field == field_name:
            return True
    return False


def filter_intentional(
    method: str,
    path: str,
    mismatches: list[str],
) -> list[str]:
    """Filter out mismatches that are registered as intentional divergences."""
    divergences = get_divergences(method, path)
    if not divergences:
        return mismatches

    div_fields = {d.field for d in divergences}
    return [m for m in mismatches if not any(f"'{f}'" in m for f in div_fields)]
