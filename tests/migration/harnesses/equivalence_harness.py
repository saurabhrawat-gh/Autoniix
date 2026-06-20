"""
Equivalence harness — compare Python vs Rust/Go responses side-by-side.

Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 1.

Usage:
    from tests.migration.harnesses.equivalence_harness import EquivalenceHarness

    h = EquivalenceHarness(python_url="http://localhost:8000", rust_url="http://localhost:8080")
    result = h.compare_signup(email="test@example.com", password="Password123!")
    assert result.equivalent
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Fields that must match between Python and Rust signup/signin responses
AUTH_FIELDS_TO_COMPARE = ["access_token", "refresh_token", "user", "workspace"]
# Fields that are allowed to differ (timestamps, tokens, IDs)
AUTH_FIELDS_IGNORE = ["expires_in", "token_type", "created_at", "updated_at"]


@dataclass
class ComparisonResult:
    """Result of comparing two service responses."""
    equivalent: bool
    status_match: bool
    body_match: bool
    python_status: int
    rust_status: int
    python_body: dict[str, Any]
    rust_body: dict[str, Any]
    mismatches: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.equivalent:
            return "✅ Equivalent (Python ↔ Rust)"
        lines = ["❌ NOT equivalent:"]
        if not self.status_match:
            lines.append(f"  Status: Python={self.python_status} vs Rust={self.rust_status}")
        for m in self.mismatches:
            lines.append(f"  {m}")
        return "\n".join(lines)


class EquivalenceHarness:
    """
    Compare Python and Rust service responses for the same logical operation.

    Does NOT require byte-identical output — only asserts on fields that
    matter for correctness. Uses divergence_registry to filter intentional
    differences.
    """

    def __init__(
        self,
        python_url: str = "http://localhost:8000",
        rust_url: str = "http://localhost:8080",
        timeout: float = 15.0,
    ):
        self.python_url = python_url
        self.rust_url = rust_url
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self) -> EquivalenceHarness:
        return self

    def __exit__(self, *_: Any) -> None:
        self.client.close()

    def close(self) -> None:
        self.client.close()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def unique_email(label: str = "equiv") -> str:
        return f"{label}-{int(time.time() * 1_000_000)}@equiv.test"

    def _check_available(self) -> tuple[bool, bool]:
        """Check if Python and Rust services are reachable and are the correct services."""
        python_ok = self._is_service_up(self.python_url, "python")
        rust_ok = self._is_service_up(self.rust_url, "rust")
        return python_ok, rust_ok

    def _is_service_up(self, url: str, expected: str) -> bool:
        """Verify a service is up and is the expected service (not Temporal UI etc)."""
        try:
            r = self.client.get(f"{url}/health", timeout=3.0)
            if r.status_code >= 500:
                return False
            # Verify it's JSON (Temporal UI returns HTML)
            content_type = r.headers.get("content-type", "")
            if "html" in content_type:
                return False
            # Try parsing as JSON
            try:
                body = r.json()
                # Rust gateway health returns JSON with status field
                if expected == "rust" and isinstance(body, dict):
                    return "status" in body or "ok" in str(body).lower()
                if expected == "python" and isinstance(body, dict):
                    return "status" in body or "components" in body or "ok" in str(body).lower()
            except Exception:
                return False
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def _compare(
        self,
        python_resp: httpx.Response,
        rust_resp: httpx.Response,
        fields_to_compare: list[str],
        endpoint: str = "",
    ) -> ComparisonResult:
        """Compare two HTTP responses."""
        python_status = python_resp.status_code
        rust_status = rust_resp.status_code

        try:
            python_body = python_resp.json()
        except Exception:
            python_body = {"_raw": python_resp.text}
        try:
            rust_body = rust_resp.json()
        except Exception:
            rust_body = {"_raw": rust_resp.text}

        status_match = python_status == rust_status
        mismatches: list[str] = []
        body_match = True

        for field_name in fields_to_compare:
            py_val = python_body.get(field_name)
            rs_val = rust_body.get(field_name)

            # Both missing = OK
            if py_val is None and rs_val is None:
                continue

            # One missing = mismatch
            if py_val is None or rs_val is None:
                mismatches.append(
                    f"Field '{field_name}': Python={'present' if py_val else 'missing'} "
                    f"vs Rust={'present' if rs_val else 'missing'}"
                )
                body_match = False
                continue

            # For token fields, just check presence (values will always differ)
            if field_name in ("access_token", "refresh_token"):
                if not py_val or not rs_val:
                    mismatches.append(f"Field '{field_name}': one or both values empty")
                    body_match = False
                continue

            # For nested objects, compare key sets
            if isinstance(py_val, dict) and isinstance(rs_val, dict):
                py_keys = set(py_val.keys())
                rs_keys = set(rs_val.keys())
                missing_in_rust = py_keys - rs_keys
                missing_in_python = rs_keys - py_keys
                if missing_in_rust:
                    mismatches.append(
                        f"Field '{field_name}': keys missing in Rust: {missing_in_rust}"
                    )
                    body_match = False
                if missing_in_python:
                    mismatches.append(
                        f"Field '{field_name}': keys missing in Python: {missing_in_python}"
                    )
                    body_match = False
                continue

            # Direct comparison
            if py_val != rs_val:
                mismatches.append(
                    f"Field '{field_name}': Python={py_val!r} vs Rust={rs_val!r}"
                )
                body_match = False

        equivalent = status_match and body_match
        return ComparisonResult(
            equivalent=equivalent,
            status_match=status_match,
            body_match=body_match,
            python_status=python_status,
            rust_status=rust_status,
            python_body=python_body,
            rust_body=rust_body,
            mismatches=mismatches,
        )

    # ── Auth endpoint comparisons ──────────────────────────────────────────

    def compare_signup(
        self,
        email: str | None = None,
        password: str = "Password123!",
        workspace_name: str = "Equiv Workspace",
        display_name: str = "Equiv User",
    ) -> ComparisonResult:
        """Compare Python /auth/register vs Rust /api/v2/auth/signup."""
        if email is None:
            email = self.unique_email("signup")

        python_resp = self.client.post(
            f"{self.python_url}/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": display_name,
                "workspace_name": workspace_name,
            },
        )
        rust_resp = self.client.post(
            f"{self.rust_url}/api/v2/auth/signup",
            json={
                "email": email,
                "password": password,
                "display_name": display_name,
                "workspace_name": workspace_name,
            },
        )

        return self._compare(
            python_resp,
            rust_resp,
            AUTH_FIELDS_TO_COMPARE,
            endpoint="signup",
        )

    def compare_signin(
        self,
        email: str,
        password: str = "Password123!",
    ) -> ComparisonResult:
        """Compare Python /auth/login vs Rust /api/v2/auth/signin."""
        python_resp = self.client.post(
            f"{self.python_url}/auth/login",
            json={"email": email, "password": password},
        )
        rust_resp = self.client.post(
            f"{self.rust_url}/api/v2/auth/signin",
            json={"email": email, "password": password},
        )

        return self._compare(
            python_resp,
            rust_resp,
            ["access_token", "refresh_token", "user"],
            endpoint="signin",
        )

    def compare_me(self, access_token: str) -> ComparisonResult:
        """Compare Python /auth/me vs Rust /api/v2/me using the same token."""
        headers = {"Authorization": f"Bearer {access_token}"}
        python_resp = self.client.get(f"{self.python_url}/auth/me", headers=headers)
        rust_resp = self.client.get(f"{self.rust_url}/api/v2/me", headers=headers)

        return self._compare(
            python_resp,
            rust_resp,
            ["email", "role", "workspace_id"],
            endpoint="me",
        )

    def compare_refresh(self, refresh_token: str) -> ComparisonResult:
        """Compare Python /auth/refresh vs Rust /api/v2/auth/refresh."""
        python_resp = self.client.post(
            f"{self.python_url}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        rust_resp = self.client.post(
            f"{self.rust_url}/api/v2/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        return self._compare(
            python_resp,
            rust_resp,
            ["access_token", "refresh_token"],
            endpoint="refresh",
        )

    # ── Generic endpoint comparison ─────────────────────────────────────────

    def compare_endpoint(
        self,
        method: str,
        python_path: str,
        rust_path: str,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        fields_to_compare: list[str] | None = None,
    ) -> ComparisonResult:
        """Generic endpoint comparison for any method/path."""
        if fields_to_compare is None:
            fields_to_compare = []

        request_kwargs: dict[str, Any] = {}
        if json_body is not None:
            request_kwargs["json"] = json_body
        if headers is not None:
            request_kwargs["headers"] = headers

        python_resp = self.client.request(
            method, f"{self.python_url}{python_path}", **request_kwargs
        )
        rust_resp = self.client.request(
            method, f"{self.rust_url}{rust_path}", **request_kwargs
        )

        return self._compare(
            python_resp,
            rust_resp,
            fields_to_compare,
            endpoint=f"{method} {python_path}",
        )

    def assert_all_equivalent(self, results: list[ComparisonResult]) -> None:
        """Assert that all comparison results are equivalent."""
        failures = []
        for r in results:
            if not r.equivalent:
                failures.append(str(r))
        if failures:
            raise AssertionError(
                f"{len(failures)} equivalence check(s) failed:\n" + "\n\n".join(failures)
            )
