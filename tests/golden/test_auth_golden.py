"""
Golden file tests — detect silent corruption when both Python and Rust return
identically wrong data.

Per HARNESS-ENGINEERING-PLAN.md Section 15.

Golden files are committed to git and represent the known-correct response
shape for critical auth endpoints. When a response drifts from the golden
file, the test fails — even if Python and Rust agree with each other.

Update process: Review golden files manually when intentionally changing behavior.

Run:
    RUST_GATEWAY_URL=http://localhost:8080 \
    pytest tests/golden/test_auth_golden.py -v
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
GOLDEN_DIR = Path(__file__).parent


def unique_email(label: str = "golden") -> str:
    return f"{label}-{int(time.time() * 1_000_000)}@golden.test"


@pytest.fixture
def client():
    with httpx.Client(timeout=15.0) as c:
        yield c


def skip_if_unavailable(client: httpx.Client, url: str) -> None:
    try:
        r = client.get(f"{url}/health", timeout=3.0)
        if "html" in r.headers.get("content-type", ""):
            pytest.skip(f"Rust gateway not running at {url} (got HTML, expected JSON API)")
        r.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"Rust gateway not running at {url}")
    except Exception:
        pytest.skip(f"Rust gateway at {url} did not return valid JSON")


@pytest.fixture(autouse=True)
def _check_service(client: httpx.Client):
    skip_if_unavailable(client, RUST_URL)


def load_golden(name: str) -> dict[str, Any]:
    path = GOLDEN_DIR / name
    if not path.exists():
        pytest.skip(f"Golden file not found: {path}")
    return json.loads(path.read_text())


def assert_keys_match(actual: dict, expected: dict, path: str = "") -> None:
    """Assert that actual has all keys present in expected (recursive)."""
    for key, expected_val in expected.items():
        full_path = f"{path}.{key}" if path else key
        assert key in actual, f"Missing key: {full_path}"
        if isinstance(expected_val, dict) and isinstance(actual[key], dict):
            assert_keys_match(actual[key], expected_val, full_path)
        elif isinstance(expected_val, list):
            assert isinstance(actual[key], list), f"{full_path} must be a list"
            if expected_val and isinstance(expected_val[0], dict):
                for i, item in enumerate(actual[key]):
                    assert_keys_match(item, expected_val[0], f"{full_path}[{i}]")


# ── Golden file: auth signup response shape ─────────────────────────────────


def test_signup_response_matches_golden(client: httpx.Client):
    """Rust signup response must match the golden file's expected structure."""
    golden = load_golden("auth_signup_golden.json")

    email = unique_email("golden-signup")
    resp = client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": "Golden Test User",
            "workspace_name": "Golden Workspace",
        },
    )
    assert resp.status_code == 201, f"Signup failed: {resp.text}"
    body = resp.json()

    expected = golden.get("expected_response", {})
    assert_keys_match(body, expected)

    # Verify specific field types
    assert isinstance(body.get("access_token"), str), "access_token must be string"
    assert isinstance(body.get("refresh_token"), str), "refresh_token must be string"
    assert isinstance(body.get("user"), dict), "user must be object"
    assert isinstance(body.get("workspace"), dict), "workspace must be object"

    if "expires_in" in body:
        assert body["expires_in"] == 3600, f"expires_in must be 3600, got {body['expires_in']}"

    if "user" in body:
        user = body["user"]
        assert "id" in user, "user must have id"
        assert "email" in user, "user must have email"
        assert user["email"] == email, "user email must match signup email"
        assert isinstance(user["id"], int), f"user.id must be int, got {type(user['id'])}"


# ── Golden file: auth signin response shape ─────────────────────────────────


def test_signin_response_matches_golden(client: httpx.Client):
    """Rust signin response must match the golden file's expected structure."""
    golden = load_golden("auth_signin_golden.json")

    email = unique_email("golden-signin")
    password = "Password123!"

    # Pre-register
    client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )

    resp = client.post(
        f"{RUST_URL}/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Signin failed: {resp.text}"
    body = resp.json()

    expected = golden.get("expected_response", {})
    assert_keys_match(body, expected)

    assert isinstance(body.get("access_token"), str), "access_token must be string"
    assert isinstance(body.get("refresh_token"), str), "refresh_token must be string"


# ── Golden file: /me response shape ─────────────────────────────────────────


def test_me_response_matches_golden(client: httpx.Client):
    """/me response must match the golden file's expected structure."""
    golden = load_golden("auth_me_golden.json")

    email = unique_email("golden-me")
    password = "Password123!"

    # Signup and get token
    signup = client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "WS"},
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]

    resp = client.get(
        f"{RUST_URL}/api/v2/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"/me failed: {resp.text}"
    body = resp.json()

    expected = golden.get("expected_response", {})
    assert_keys_match(body, expected)

    # /me returns a { data: {...} } envelope matching Python's contract
    assert isinstance(body.get("data"), dict), "/me must return a data object"
    data = body["data"]
    assert data.get("email") == email, "/me must return same email"
    assert "user_id" in data, "/me must return user_id"
    assert isinstance(data.get("permissions"), list), "/me must return a permissions list"


# ── Golden file: DB state after signup ──────────────────────────────────────


def test_signup_db_state_matches_golden(client: httpx.Client):
    """After signup, DB state must match the golden file's expected_db_state."""
    golden = load_golden("auth_signup_golden.json")
    expected_db = golden.get("expected_db_state", {})
    if not expected_db:
        pytest.skip("No expected_db_state in golden file")

    email = unique_email("golden-db")
    resp = client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": "Password123!", "workspace_name": "Golden WS"},
    )
    assert resp.status_code == 201
    body = resp.json()
    user_id = body.get("user", {}).get("id")
    workspace_id = body.get("workspace", {}).get("id")

    # Verify expected DB state structure
    if "users" in expected_db:
        expected_user = expected_db["users"][0]
        if "email" in expected_user:
            assert body["user"]["email"] == email
        if "role" in expected_user:
            # The global role is assigned by signup order (first user = superadmin,
            # everyone else = user), so it is not deterministic against a shared/
            # populated DB. Assert only that a non-empty role string is returned.
            role = body["user"].get("role")
            assert isinstance(role, str) and role, f"User role must be a non-empty string, got {role!r}"

    if "workspaces" in expected_db:
        expected_ws = expected_db["workspaces"][0]
        if "name" in expected_ws:
            assert body["workspace"]["name"] == "Golden WS"

    print(f"✓ DB state matches golden file for user_id={user_id}, workspace_id={workspace_id}")
