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


# Registry of intentional divergences, keyed by "METHOD /path"
#
# NOTE: The auth contract-divergence audit (2026-06-20) found that the Rust
# gateway is NOT yet a drop-in replacement for the Python dashboard. The
# entries below tagged "PENDING-ALIGNMENT" are NOT approved/intentional — they
# are KNOWN OPEN gaps recorded here so the equivalence harness does not fail
# constantly while the alignment work is scheduled. Each references the GitHub
# issue that tracks closing the gap. Remove the entry when its issue lands.
INTENTIONAL_DIVERGENCES: dict[str, list[Divergence]] = {
    # Register response shape (no tokens) and /register canonical path were
    # aligned by #350; password policy (min 8 chars, no complexity rule) is
    # now identical between Python and Rust. /signup remains as a Rust-only
    # backward-compatible alias for /register — deprecated, returns the same
    # body. There are no known intentional divergences for register at this time.
    "POST /api/v2/auth/register": [],

    # GET /api/v2/users (superadmin-only user list) is a fresh port: Rust
    # uses the exact same SQL as Python so the response is byte-for-byte
    # identical. No intentional divergences.
    "GET /api/v2/users": [],
    # POST /api/v2/users/transfer-superadmin/{id} — atomic role swap inside
    # a transaction. Rust mirrors Python's error semantics (400/404/409) and
    # the "user.superadmin.transfer" audit action verbatim.
    "POST /api/v2/users/transfer-superadmin": [],
    # PUT /api/v2/users/{id}/disable — disables account + revokes sessions.
    # Same 403 ("You cannot disable your own account") and 403 superadmin
    # guard messages as Python.
    "PUT /api/v2/users/disable": [],
    # PUT /api/v2/users/{id}/enable — idempotent re-enable. No edge cases.
    "PUT /api/v2/users/enable": [],
    # DELETE /api/v2/users/{id} — tombstone the user row with
    # deleted-{id}@deleted.local sentinel email + cascade clean-up (sessions
    # revoked, workspace_members cleared). Mirrors Python's three-statement
    # transaction byte-for-byte.
    "DELETE /api/v2/users": [],

    # GET /api/v2/flags — feature flag catalog, any authenticated user.
    # PUT /api/v2/flags/{key} — owner/member only, 404 on unknown key,
    # audits `flag.update` with before/after payloads. Both byte-for-byte
    # ports of `v2/flags.py`.
    "GET /api/v2/flags": [],
    "PUT /api/v2/flags": [],

    # GET /api/v2/notifications — list (any authed user); supports
    # `unread_only`, `severity`, `limit` query params.
    "GET /api/v2/notifications": [],
    # POST /api/v2/notifications — owner/member; 60s dedupe window.
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
    # POST /api/v2/notifications/{id}/read — idempotent append to read_by.
    "POST /api/v2/notifications/read": [],
    # GET /api/v2/notifications/routes — list routes (owner/member).
    "GET /api/v2/notifications/routes": [],
    # POST /api/v2/notifications/routes — create + audit `notification.route.create`.
    "POST /api/v2/notifications/routes": [],
    # PUT /api/v2/notifications/routes/{id} — replace; 404 on missing row.
    "PUT /api/v2/notifications/routes": [],
    # DELETE /api/v2/notifications/routes/{id} — drop + audit `notification.route.delete`.
    # No 404 — matches Python's always-200 behavior.
    "DELETE /api/v2/notifications/routes": [],
    # GET /api/v2/notifications/deliveries — owner/member; optional
    # `notification_id` filter narrows the result set.
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
        # status field + workspace_id naming aligned by #646; refresh-token cookie
        # alignment resolved by #644 (cookie-only on both sides).
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
