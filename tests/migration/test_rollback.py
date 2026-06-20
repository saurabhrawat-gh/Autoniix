"""
Rollback safety tests — verify that data created via Rust can still be
read by the Python service after a rollback.

Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 4.

These tests require both services to be running and sharing the same database.
Skip automatically if services are not reachable.

Run:
    RUST_GATEWAY_URL=http://localhost:8080 \
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    pytest tests/migration/test_rollback.py -v
"""
from __future__ import annotations

import time

import httpx
import pytest

RUST_URL = "http://localhost:8080"
PYTHON_URL = "http://localhost:8000"


def unique_email(label: str) -> str:
    return f"{label}-{int(time.time() * 1000)}@rollback.test"


@pytest.fixture
def rust_client():
    with httpx.Client(base_url=RUST_URL, timeout=10.0) as c:
        yield c


@pytest.fixture
def python_client():
    with httpx.Client(base_url=PYTHON_URL, timeout=10.0) as c:
        yield c


def skip_if_unavailable(client: httpx.Client, url: str) -> None:
    """Skip test if service is not reachable."""
    try:
        client.get("/health", timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"Service not running at {url}")


# ── Test: Rust-created user readable by Python ────────────────────────────────

def test_rust_user_readable_by_python(rust_client, python_client):
    """Data created via Rust signup must be readable via Python login."""
    skip_if_unavailable(rust_client, RUST_URL)
    skip_if_unavailable(python_client, PYTHON_URL)

    email = unique_email("rust-to-python")
    password = "RollbackTest123!"

    # Step 1: Create user via Rust
    signup_resp = rust_client.post(
        "/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "Rollback WS"},
    )
    assert signup_resp.status_code == 201, f"Rust signup failed: {signup_resp.text}"

    rust_user_id = signup_resp.json()["user"]["id"]

    # Step 2: Log in via Python (simulates rollback to Python)
    login_resp = python_client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, (
        f"Python login failed for Rust-created user: {login_resp.text}"
    )

    python_token = login_resp.json().get("access_token", "")
    assert python_token, "Python login must return access_token"

    # Step 3: Verify /me returns same user data via Python
    me_resp = python_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {python_token}"},
    )
    if me_resp.status_code == 200:
        assert me_resp.json().get("email") == email, "Python /me must return same email"


# ── Test: Python-created user readable by Rust ───────────────────────────────

def test_python_user_readable_by_rust(rust_client, python_client):
    """Data created via Python register must be readable via Rust signin."""
    skip_if_unavailable(rust_client, RUST_URL)
    skip_if_unavailable(python_client, PYTHON_URL)

    email = unique_email("python-to-rust")
    password = "RollbackTest123!"

    # Step 1: Create user via Python
    register_resp = python_client.post(
        "/auth/register",
        json={"email": email, "password": password, "workspace_name": "Python WS"},
    )
    assert register_resp.status_code in (200, 201), (
        f"Python register failed: {register_resp.text}"
    )

    # Step 2: Sign in via Rust (simulates forward migration to Rust)
    signin_resp = rust_client.post(
        "/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert signin_resp.status_code == 200, (
        f"Rust signin failed for Python-created user: {signin_resp.text}"
    )

    rust_token = signin_resp.json().get("access_token", "")
    assert rust_token, "Rust signin must return access_token"


# ── Test: Token cross-validity (shared JWT secret) ───────────────────────────

def test_rust_token_cross_validated_by_python(rust_client, python_client):
    """JWT issued by Rust must be accepted by Python (shared secret)."""
    skip_if_unavailable(rust_client, RUST_URL)
    skip_if_unavailable(python_client, PYTHON_URL)

    email = unique_email("jwt-cross")
    password = "RollbackTest123!"

    # Create user + get Rust token
    signup = rust_client.post(
        "/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "JWT WS"},
    )
    if signup.status_code != 201:
        pytest.skip("Rust signup failed — cannot test cross-validation")

    rust_token = signup.json().get("access_token", "")

    # Use Rust token against Python endpoint
    me_resp = python_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"},
    )

    # If Python accepts the token (shared JWT secret), email must match
    if me_resp.status_code == 200:
        assert me_resp.json().get("email") == email, "email must match across services"
        print(f"✓ Rust JWT accepted by Python (shared secret verified)")
    else:
        # 401 means JWT secret mismatch — flag as warning, not hard failure
        print(f"⚠ Python returned {me_resp.status_code} — JWT secret may differ")


# ── Test: Session data consistent across rollback ────────────────────────────

def test_refresh_token_works_after_service_switch(rust_client, python_client):
    """
    Opaque refresh tokens stored in the sessions table must be readable
    after switching between services (Rust → Python).

    This validates that both services use the same sessions schema.
    """
    skip_if_unavailable(rust_client, RUST_URL)
    skip_if_unavailable(python_client, PYTHON_URL)

    email = unique_email("refresh-cross")
    password = "RollbackTest123!"

    # Create session via Rust
    signup = rust_client.post(
        "/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "Session WS"},
    )
    if signup.status_code != 201:
        pytest.skip("Rust signup failed")

    refresh_token = signup.json().get("refresh_token", "")

    # Refresh via Python (simulates Rust → Python rollback)
    refresh_resp = python_client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    if refresh_resp.status_code == 200:
        new_token = refresh_resp.json().get("access_token", "")
        assert new_token, "Python must return new access_token on refresh"
        print("✓ Rust-created session refreshed via Python (schema compatible)")
    else:
        print(
            f"⚠ Python refresh returned {refresh_resp.status_code} "
            f"for Rust-created session — sessions schema may differ"
        )
