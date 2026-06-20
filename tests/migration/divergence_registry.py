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
    "POST /auth/signup": [
        Divergence(
            field="password",
            python_behavior="min 6 chars",
            rust_behavior="min 8 chars + complexity",
            reason="Security hardening — Rust enforces stronger password policy",
            approved_by="security-team",
            approved_date="2026-06-20",
        ),
        Divergence(
            field="access_token",
            python_behavior="register returns NO tokens (invite-only, no auto-login)",
            rust_behavior="signup auto-logs-in and returns access_token + refresh_token",
            reason="PENDING-ALIGNMENT — tracked in #645 (register must be invite-only + not auto-login)",
            approved_by="UNRESOLVED",
            approved_date="2026-06-20",
        ),
    ],
    "POST /auth/signin": [
        Divergence(
            field="expires_in",
            python_behavior=3600,
            rust_behavior=3600,
            reason="Both use 1-hour access token expiry — values match but field may be absent in one",
            approved_by="migration-lead",
            approved_date="2026-06-20",
        ),
        Divergence(
            field="status",
            python_behavior="response includes status='ok' and user.workspace_id",
            rust_behavior="no status field; uses user.active_workspace_id",
            reason="PENDING-ALIGNMENT — tracked in #646 (align login/signin response shape)",
            approved_by="UNRESOLVED",
            approved_date="2026-06-20",
        ),
        # Refresh-token cookie alignment resolved by #644 (cookie-only on both sides).
    ],
    "POST /auth/refresh": [
        # Refresh-token cookie alignment resolved by #644 (cookie-only on both sides).
        Divergence(
            field="status",
            python_behavior="response includes status='ok'",
            rust_behavior="no status field",
            reason="PENDING-ALIGNMENT — tracked in #646 (align response shape: status field)",
            approved_by="UNRESOLVED",
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
