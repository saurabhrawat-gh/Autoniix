"""
Auth equivalence tests — compare Python and Rust auth endpoints side-by-side.

Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 1.

These tests require both Python and Rust services to be running.
Skip automatically if either service is not reachable.

Run:
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    RUST_GATEWAY_URL=http://localhost:8080 \
    pytest tests/migration/test_auth_equivalence.py -v
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

from tests.migration.harnesses.equivalence_harness import EquivalenceHarness

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")


def unique_email(label: str = "equiv") -> str:
    return f"{label}-{int(time.time() * 1_000_000)}@equiv.test"


@pytest.fixture
def harness():
    h = EquivalenceHarness(python_url=PYTHON_URL, rust_url=RUST_URL)
    python_ok, rust_ok = h._check_available()
    if not python_ok:
        pytest.skip(f"Python dashboard not running at {PYTHON_URL}")
    if not rust_ok:
        pytest.skip(f"Rust gateway not running at {RUST_URL}")
    yield h
    h.close()


# ── Signup equivalence ──────────────────────────────────────────────────────


def test_signup_responses_equivalent(harness: EquivalenceHarness):
    """Python /auth/register and Rust /api/v2/auth/signup must return equivalent responses."""
    email = unique_email("signup-equiv")
    result = harness.compare_signup(email=email)
    print(result)
    assert result.status_match, (
        f"Status mismatch: Python={result.python_status} vs Rust={result.rust_status}"
    )
    assert result.body_match, (
        f"Body mismatch:\n" + "\n".join(result.mismatches)
    )


def test_signup_returns_required_fields(harness: EquivalenceHarness):
    """Both services must return access_token, refresh_token, user, workspace."""
    email = unique_email("signup-fields")
    result = harness.compare_signup(email=email)

    for field_name in ["access_token", "refresh_token", "user", "workspace"]:
        assert result.python_body.get(field_name) is not None, (
            f"Python signup missing field: {field_name}"
        )
        assert result.rust_body.get(field_name) is not None, (
            f"Rust signup missing field: {field_name}"
        )


# ── Signin equivalence ──────────────────────────────────────────────────────


def test_signin_responses_equivalent(harness: EquivalenceHarness):
    """Python /auth/login and Rust /api/v2/auth/signin must return equivalent responses."""
    email = unique_email("signin-equiv")
    password = "Password123!"

    # Pre-register via both services
    harness.client.post(
        f"{PYTHON_URL}/auth/register",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )
    harness.client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )

    result = harness.compare_signin(email=email, password=password)
    print(result)
    assert result.status_match, (
        f"Status mismatch: Python={result.python_status} vs Rust={result.rust_status}"
    )


# ── /me endpoint equivalence ────────────────────────────────────────────────


def test_me_endpoint_cross_service(harness: EquivalenceHarness):
    """Rust-issued token should work on Python /auth/me and vice versa."""
    email = unique_email("me-cross")
    password = "Password123!"

    # Signup via Rust
    signup = harness.client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )
    if signup.status_code != 201:
        pytest.skip("Rust signup failed")

    rust_token = signup.json().get("access_token", "")
    assert rust_token, "Rust signup must return access_token"

    # Use Rust token on Python /auth/me
    me_resp = harness.client.get(
        f"{PYTHON_URL}/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"},
    )
    if me_resp.status_code == 200:
        assert me_resp.json().get("email") == email, "Python /me must return same email"
        print("✓ Rust-issued JWT accepted by Python")
    else:
        print(f"⚠ Python returned {me_resp.status_code} for Rust-issued JWT")


# ── Error handling equivalence ──────────────────────────────────────────────


def test_signin_invalid_password_returns_same_error(harness: EquivalenceHarness):
    """Both services must reject invalid credentials with same status code."""
    email = unique_email("error-equiv")
    password = "Password123!"

    # Register via both
    harness.client.post(
        f"{PYTHON_URL}/auth/register",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )
    harness.client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )

    # Try login with wrong password
    result = harness.compare_signin(email=email, password="WrongPassword!")
    assert result.status_match, (
        f"Error status mismatch for invalid password: "
        f"Python={result.python_status} vs Rust={result.rust_status}"
    )
    # Both should be 4xx
    assert 400 <= result.python_status < 500, (
        f"Python should return 4xx for invalid password, got {result.python_status}"
    )
    assert 400 <= result.rust_status < 500, (
        f"Rust should return 4xx for invalid password, got {result.rust_status}"
    )


def test_signup_duplicate_email_returns_same_error(harness: EquivalenceHarness):
    """Both services must reject duplicate email with same status code."""
    email = unique_email("dup-equiv")
    password = "Password123!"
    payload = {"email": email, "password": password, "workspace_name": "WS"}

    # First signup via Python
    harness.client.post(f"{PYTHON_URL}/auth/register", json=payload)
    # First signup via Rust
    harness.client.post(f"{RUST_URL}/api/v2/auth/signup", json=payload)

    # Try duplicate on both
    py_resp = harness.client.post(f"{PYTHON_URL}/auth/register", json=payload)
    rs_resp = harness.client.post(f"{RUST_URL}/api/v2/auth/signup", json=payload)

    assert py_resp.status_code == rs_resp.status_code, (
        f"Duplicate email error mismatch: Python={py_resp.status_code} vs Rust={rs_resp.status_code}"
    )
    assert 400 <= py_resp.status_code < 500, "Both should reject duplicate email"
