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

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL") or "http://localhost:8000"
RUST_URL = os.getenv("RUST_GATEWAY_URL") or "http://localhost:8080"


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


# ── Register equivalence (post-#350) ────────────────────────────────────────


def test_register_responses_equivalent(harness: EquivalenceHarness):
    """Python and Rust /api/v2/auth/register must return equivalent responses.
    Post-#350: both share the canonical /register path and the same
    onboarding-metadata body shape (no tokens)."""
    email = unique_email("register-equiv")
    result = harness.compare_register(email=email)
    print(result)
    assert result.status_match, (
        f"Status mismatch: Python={result.python_status} vs Rust={result.rust_status}"
    )
    assert result.body_match, (
        "Body mismatch:\n" + "\n".join(result.mismatches)
    )


def test_register_returns_required_fields(harness: EquivalenceHarness):
    """Both services must return status, user_id, workspace_id, role, onboarding_required.
    Post-#350: register no longer returns tokens — frontend signs in separately."""
    email = unique_email("register-fields")
    result = harness.compare_register(email=email)

    for field_name in ["status", "user_id", "workspace_id", "role", "onboarding_required"]:
        assert result.python_body.get(field_name) is not None, (
            f"Python register missing field: {field_name}"
        )
        assert result.rust_body.get(field_name) is not None, (
            f"Rust register missing field: {field_name}"
        )

    # Tokens MUST NOT be returned (would defeat the email-verification flow
    # implied by onboarding_required=true).
    for forbidden in ["access_token", "refresh_token"]:
        assert result.python_body.get(forbidden) is None, (
            f"Python register must not return {forbidden} (post-#350)"
        )
        assert result.rust_body.get(forbidden) is None, (
            f"Rust register must not return {forbidden} (post-#350)"
        )


# ── Signin equivalence ──────────────────────────────────────────────────────


def test_signin_responses_equivalent(harness: EquivalenceHarness):
    """Python /api/v2/auth/login and Rust /api/v2/auth/signin must return equivalent responses."""
    email = unique_email("signin-equiv")
    password = "Password123!"

    # Pre-register via both services (each gets its own row — user_id
    # differs but the email/password verification logic is what's under test)
    body = {
        "email": email,
        "password": password,
        "display_name": "Signin Equiv",
        "workspace_name": "WS",
    }
    harness.client.post(f"{PYTHON_URL}/api/v2/auth/register", json=body)
    harness.client.post(f"{RUST_URL}/api/v2/auth/register", json=body)

    result = harness.compare_signin(email=email, password=password)
    print(result)
    assert result.status_match, (
        f"Status mismatch: Python={result.python_status} vs Rust={result.rust_status}"
    )


# ── /me endpoint equivalence ────────────────────────────────────────────────


def test_me_endpoint_cross_service(harness: EquivalenceHarness):
    """Rust-issued token must work on Python /api/v2/auth/me.
    Post-#350: register no longer returns tokens, so we register + signin
    explicitly to obtain a token, then replay it across services."""
    email = unique_email("me-cross")
    password = "Password123!"

    register = harness.client.post(
        f"{RUST_URL}/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Me Cross",
            "workspace_name": "WS",
        },
    )
    if register.status_code != 201:
        pytest.skip(f"Rust register failed: {register.status_code} {register.text}")

    signin = harness.client.post(
        f"{RUST_URL}/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    if signin.status_code != 200:
        pytest.skip(f"Rust signin failed: {signin.status_code} {signin.text}")
    rust_token = signin.json().get("access_token", "")
    assert rust_token, "Rust signin must return access_token"

    # Use Rust token on Python /api/v2/auth/me
    me_resp = harness.client.get(
        f"{PYTHON_URL}/api/v2/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"},
    )
    assert me_resp.status_code == 200, (
        f"Python /me must accept Rust-issued JWT (got {me_resp.status_code}: "
        f"{me_resp.text}). Check AUTH_JWT_SECRET is shared."
    )
    body = me_resp.json()
    me_email = (body.get("data") or {}).get("email") or body.get("email")
    assert me_email == email, (
        f"Python /me must return same email: expected {email}, got {me_email}"
    )


# ── Error handling equivalence ──────────────────────────────────────────────


def test_signin_invalid_password_returns_same_error(harness: EquivalenceHarness):
    """Both services must reject invalid credentials with same status code."""
    email = unique_email("error-equiv")
    password = "Password123!"
    body = {
        "email": email,
        "password": password,
        "display_name": "Err Equiv",
        "workspace_name": "WS",
    }

    harness.client.post(f"{PYTHON_URL}/api/v2/auth/register", json=body)
    harness.client.post(f"{RUST_URL}/api/v2/auth/register", json=body)

    # Try login with wrong password
    result = harness.compare_signin(email=email, password="WrongPassword!")
    assert result.status_match, (
        f"Error status mismatch for invalid password: "
        f"Python={result.python_status} vs Rust={result.rust_status}"
    )
    assert 400 <= result.python_status < 500, (
        f"Python should return 4xx for invalid password, got {result.python_status}"
    )
    assert 400 <= result.rust_status < 500, (
        f"Rust should return 4xx for invalid password, got {result.rust_status}"
    )


def test_register_duplicate_email_returns_same_error(harness: EquivalenceHarness):
    """Both services must reject duplicate email with same status code.
    Per #350 contract, both should return 409."""
    email = unique_email("dup-equiv")
    payload = {
        "email": email,
        "password": "Password123!",
        "display_name": "Dup Equiv",
        "workspace_name": "WS",
    }

    # First registration on each service (one DB row per service in shared DB,
    # but the duplicate-detection lookup is what's under test)
    harness.client.post(f"{PYTHON_URL}/api/v2/auth/register", json=payload)
    harness.client.post(f"{RUST_URL}/api/v2/auth/register", json=payload)

    # Duplicate attempt should return 409 on both
    py_resp = harness.client.post(f"{PYTHON_URL}/api/v2/auth/register", json=payload)
    rs_resp = harness.client.post(f"{RUST_URL}/api/v2/auth/register", json=payload)

    assert py_resp.status_code == rs_resp.status_code, (
        f"Duplicate email error mismatch: "
        f"Python={py_resp.status_code} vs Rust={rs_resp.status_code}"
    )
    assert py_resp.status_code == 409, (
        f"Both services must return 409 on duplicate email, got {py_resp.status_code}"
    )
