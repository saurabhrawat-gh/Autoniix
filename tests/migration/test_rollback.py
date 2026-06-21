"""
Rollback safety tests — verify that data created via Rust can still be
read by the Python service after a rollback (and vice-versa).

Per HARNESS-ENGINEERING-PLAN.md Section 11 (Production Rollout Strategy).

Scenario:
  Both services share the SAME database. The migration uses per-endpoint
  feature flags (auth.v2.enabled). To roll back, we flip a flag and route
  traffic back to Python. These tests prove that data written by one
  service is consumable by the other — no data loss, no re-auth required.

Post-#350: /register returns onboarding metadata only (no tokens). The
frontend (and these tests) must call /login (Python) or /signin (Rust)
separately to obtain a session.

Requires both services running against the same database. Skips when
either is unreachable so the suite passes in environments where only one
service is up (e.g. PR CI for the Rust crate).

Run:
    RUST_GATEWAY_URL=http://localhost:8080 \
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    pytest tests/migration/test_rollback.py -v
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")


def unique_email(label: str) -> str:
    # Use ns precision + a label to keep emails unique across parametrize runs
    return f"{label}-{time.time_ns()}@rollback.test"


@pytest.fixture
def rust_client():
    with httpx.Client(base_url=RUST_URL, timeout=10.0) as c:
        yield c


@pytest.fixture
def python_client():
    with httpx.Client(base_url=PYTHON_URL, timeout=10.0) as c:
        yield c


def _skip_if_unavailable(client: httpx.Client, url: str, health_path: str) -> None:
    """Skip test if service is not reachable on the given health path."""
    try:
        r = client.get(health_path, timeout=2.0)
        if r.status_code >= 500:
            pytest.skip(f"Service at {url} returned {r.status_code} on {health_path}")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        pytest.skip(f"Service not running at {url}")


def skip_unless_both_up(rust: httpx.Client, py: httpx.Client) -> None:
    """Convenience: skip when either service is unreachable.

    Rust gateway exposes `/health/live`; Python dashboard exposes `/health`.
    """
    _skip_if_unavailable(rust, RUST_URL, "/health/live")
    _skip_if_unavailable(py, PYTHON_URL, "/health")


# ── Helpers: register + signin via each service ───────────────────────────────

WS_NAME = "Rollback WS"


def _rust_register(client: httpx.Client, email: str, password: str) -> dict:
    """Create a user + workspace via Rust. Returns the onboarding metadata
    (status, user_id, workspace_id, role, onboarding_required)."""
    r = client.post(
        "/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Rollback User",
            "workspace_name": WS_NAME,
        },
    )
    assert r.status_code == 201, f"Rust register failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("status") == "ok"
    return body


def _python_register(client: httpx.Client, email: str, password: str) -> dict:
    """Create a user + workspace via Python. Returns the onboarding metadata."""
    r = client.post(
        "/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Rollback User",
            "workspace_name": WS_NAME,
        },
    )
    assert r.status_code in (200, 201), (
        f"Python register failed: {r.status_code} {r.text}"
    )
    body = r.json()
    assert body.get("status") == "ok"
    return body


def _rust_signin(client: httpx.Client, email: str, password: str) -> dict:
    r = client.post(
        "/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, f"Rust signin failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("access_token"), "Rust signin must return access_token"
    return body


def _python_login(client: httpx.Client, email: str, password: str) -> dict:
    r = client.post(
        "/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, f"Python login failed: {r.status_code} {r.text}"
    body = r.json()
    return body


# ── TC-RB-01: Rust-created user can log in via Python (Rust → Python rollback) ──

def test_rust_user_can_login_via_python(rust_client, python_client):
    """User registered via Rust must be able to log in via Python after a
    rollback. Validates that the users + workspaces + workspace_members
    rows written by Rust are readable + verifiable by Python's auth path
    (same Argon2 hash format, same schema)."""
    skip_unless_both_up(rust_client, python_client)

    email = unique_email("rust-to-py")
    password = "RollbackTest123!"

    _rust_register(rust_client, email, password)
    py_session = _python_login(python_client, email, password)

    user = py_session.get("user") or {}
    assert user.get("email", "").lower() == email.lower(), (
        "Python login must return the same email Rust registered"
    )


# ── TC-RB-02: Python-created user can sign in via Rust (forward migration) ──

def test_python_user_can_signin_via_rust(rust_client, python_client):
    """User registered via Python must be able to sign in via Rust after
    the migration cuts over. Validates the reverse direction — same
    requirement, both Argon2 verifiers must accept each other's hashes."""
    skip_unless_both_up(rust_client, python_client)

    email = unique_email("py-to-rust")
    password = "RollbackTest123!"

    _python_register(python_client, email, password)
    rust_session = _rust_signin(rust_client, email, password)

    user = rust_session.get("user") or {}
    assert user.get("email", "").lower() == email.lower(), (
        "Rust signin must return the same email Python registered"
    )


# ── TC-RB-03: Rust-issued JWT accepted by Python /me (shared secret) ─────────

def test_rust_jwt_accepted_by_python_me(rust_client, python_client):
    """JWT issued by Rust /signin must be accepted by Python /me.
    Requires both services to share AUTH_JWT_SECRET. During a mid-traffic
    rollback, in-flight Rust-issued tokens must keep working against
    Python — otherwise every active user gets force-logged-out."""
    skip_unless_both_up(rust_client, python_client)

    email = unique_email("jwt-cross")
    password = "RollbackTest123!"

    _rust_register(rust_client, email, password)
    rust_session = _rust_signin(rust_client, email, password)
    rust_token = rust_session["access_token"]

    me_resp = python_client.get(
        "/api/v2/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"},
    )
    assert me_resp.status_code == 200, (
        f"Python /me must accept Rust-issued JWT (got {me_resp.status_code}: "
        f"{me_resp.text}). If 401, AUTH_JWT_SECRET differs between services."
    )
    body = me_resp.json()
    me_email = (body.get("data") or {}).get("email") or body.get("email")
    assert (me_email or "").lower() == email.lower(), (
        f"Python /me returned wrong email: expected {email}, got {me_email}"
    )


# ── TC-RB-04: Python-issued JWT accepted by Rust /me (reverse direction) ────

def test_python_jwt_accepted_by_rust_me(rust_client, python_client):
    """JWT issued by Python /login must be accepted by Rust /me. During
    the forward migration, in-flight Python-issued tokens must keep
    working against Rust — same kill-switch invariant in reverse."""
    skip_unless_both_up(rust_client, python_client)

    email = unique_email("jwt-cross-rev")
    password = "RollbackTest123!"

    _python_register(python_client, email, password)
    py_session = _python_login(python_client, email, password)
    py_token = py_session.get("access_token")
    if not py_token:
        pytest.skip("Python login did not return access_token in body (cookie-only mode)")

    me_resp = rust_client.get(
        "/api/v2/me",
        headers={"Authorization": f"Bearer {py_token}"},
    )
    assert me_resp.status_code == 200, (
        f"Rust /me must accept Python-issued JWT (got {me_resp.status_code}: "
        f"{me_resp.text}). If 401, AUTH_JWT_SECRET differs between services."
    )
    body = me_resp.json()
    me_email = (body.get("data") or {}).get("email") or body.get("email")
    assert (me_email or "").lower() == email.lower(), (
        f"Rust /me returned wrong email: expected {email}, got {me_email}"
    )


# ── TC-RB-05: Refresh token issued by Rust can be rotated via Python ───────

def test_rust_refresh_token_rotates_via_python(rust_client, python_client):
    """Opaque refresh tokens written to the sessions table by Rust must be
    rotatable by Python (sha256 hash + sessions row schema must match).
    This is the riskiest rollback path — if it breaks, every active user
    loses their session on rollback.

    The refresh token comes back as an HttpOnly cookie on signin. We pull
    it from the cookie jar and replay it against Python's /refresh."""
    skip_unless_both_up(rust_client, python_client)

    email = unique_email("refresh-cross")
    password = "RollbackTest123!"

    _rust_register(rust_client, email, password)
    signin = rust_client.post(
        "/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert signin.status_code == 200, f"Rust signin failed: {signin.text}"

    refresh = signin.cookies.get("refresh_token")
    assert refresh, (
        "Rust signin must set refresh_token cookie — cannot test cross-service "
        "refresh without it"
    )

    rotated = python_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert rotated.status_code == 200, (
        f"Python /refresh must rotate Rust-issued session (got {rotated.status_code}: "
        f"{rotated.text}). If 401, sessions table schema or sha256 hashing differs."
    )
    body = rotated.json()
    assert body.get("access_token"), "Python /refresh must return a new access_token"


# ── TC-RB-06: Feature flag flip is observable via /auth/mode ──────────────

def test_auth_mode_endpoint_reports_flag_state(rust_client, python_client):
    """The kill-switch flag (auth.v2.enabled) must be queryable via
    /api/v2/auth/mode on both services. The frontend reads this on mount
    to know which backend is serving auth; during a rollback drill we
    verify both sides agree on the current flag state.

    This is the smoke test for the rollback mechanism itself — if the
    flag isn't readable, we can't roll back without a deploy."""
    skip_unless_both_up(rust_client, python_client)

    rust_mode = rust_client.get("/api/v2/auth/mode")
    assert rust_mode.status_code == 200, f"Rust /auth/mode unreachable: {rust_mode.text}"
    rust_body = rust_mode.json()
    assert "v2_enabled" in rust_body, "Rust /auth/mode must expose v2_enabled"
    assert "legacy_enabled" in rust_body, "Rust /auth/mode must expose legacy_enabled"

    py_mode = python_client.get("/api/v2/auth/mode")
    assert py_mode.status_code == 200, f"Python /auth/mode unreachable: {py_mode.text}"
    py_body = py_mode.json()
    assert "v2_enabled" in py_body
    assert "legacy_enabled" in py_body

    # Both services read from the same feature_flags table — their view
    # of the kill-switch must be identical at any point in time.
    assert rust_body["v2_enabled"] == py_body["v2_enabled"], (
        f"Rust and Python disagree on auth.v2.enabled: "
        f"rust={rust_body['v2_enabled']} python={py_body['v2_enabled']}. "
        "Rollback flag flip would be inconsistent."
    )
    assert rust_body["legacy_enabled"] == py_body["legacy_enabled"], (
        "Rust and Python disagree on auth.legacy.enabled — same problem"
    )
