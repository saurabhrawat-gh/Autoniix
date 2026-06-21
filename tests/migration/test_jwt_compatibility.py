"""
JWT cross-compatibility tests — verify tokens are interchangeable between Python and Rust.

Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 1 (JWT fix) + Week 4 Day 1.

Requires both services running with the same AUTH_JWT_SECRET.
Skip automatically if services are not reachable.

Run:
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    RUST_GATEWAY_URL=http://localhost:8080 \
    pytest tests/migration/test_jwt_compatibility.py -v
"""
from __future__ import annotations

import os
import time

import httpx
import jwt
import pytest

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "test-jwt-secret")
JWT_ALGORITHM = "HS256"


def unique_email(label: str = "jwt") -> str:
    return f"{label}-{int(time.time() * 1_000_000)}@jwt.test"


@pytest.fixture
def client():
    with httpx.Client(timeout=15.0) as c:
        yield c


def skip_if_unavailable(client: httpx.Client, url: str, label: str) -> None:
    try:
        r = client.get(f"{url}/health", timeout=3.0)
        # Reject HTML responses (e.g. Temporal UI on port 8080)
        if "html" in r.headers.get("content-type", ""):
            pytest.skip(f"{label} not running at {url} (got HTML, expected JSON API)")
        r.json()  # Must be JSON
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"{label} not running at {url}")
    except Exception:
        pytest.skip(f"{label} at {url} did not return valid JSON")


@pytest.fixture(autouse=True)
def _check_services(client: httpx.Client):
    skip_if_unavailable(client, PYTHON_URL, "Python dashboard")
    skip_if_unavailable(client, RUST_URL, "Rust gateway")


# ── Token structure validation ──────────────────────────────────────────────


def test_rust_jwt_claims_match_python_schema(client: httpx.Client):
    """Rust-issued JWT must have same claim structure as Python's."""
    email = unique_email("rust-claims")
    password = "Password123!"

    # Register via Rust (post-#350: no auto-login, need explicit signin)
    register = client.post(
        f"{RUST_URL}/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "JWT Claims",
            "workspace_name": "WS",
        },
    )
    assert register.status_code == 201, f"Rust register failed: {register.text}"

    signin = client.post(
        f"{RUST_URL}/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert signin.status_code == 200, f"Rust signin failed: {signin.text}"

    token = signin.json()["access_token"]
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    # Required fields per Python schema
    assert "sub" in claims, "JWT missing 'sub' claim"
    assert "email" in claims, "JWT missing 'email' claim"
    assert "role" in claims, "JWT missing 'role' claim"
    assert "wid" in claims, "JWT missing 'wid' claim"
    assert "exp" in claims, "JWT missing 'exp' claim"

    # sub must be parseable as int (Python does int(claims["sub"]))
    sub = claims["sub"]
    if isinstance(sub, str):
        int(sub)  # Must not raise
    elif isinstance(sub, int):
        pass
    else:
        pytest.fail(f"JWT 'sub' must be int or stringified int, got {type(sub)}")

    # wid must be int
    assert isinstance(claims["wid"], int), f"JWT 'wid' must be int, got {type(claims['wid'])}"

    # role must be string (not array)
    assert isinstance(claims["role"], str), f"JWT 'role' must be string, got {type(claims['role'])}"

    assert claims["email"] == email, "JWT email must match signup email"


def test_python_jwt_claims_match_rust_schema(client: httpx.Client):
    """Python-issued JWT must be decodable by Rust (same claim structure)."""
    email = unique_email("py-claims")
    password = "Password123!"

    # Register via Python, then login (post-#350: register returns no tokens)
    register = client.post(
        f"{PYTHON_URL}/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "JWT Claims",
            "workspace_name": "WS",
        },
    )
    assert register.status_code in (200, 201), f"Python register failed: {register.text}"

    login = client.post(
        f"{PYTHON_URL}/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Python login failed: {login.text}"

    token = login.json()["access_token"]
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    # Rust expects: sub (string), email, role, global_role, wid (i64)
    assert "sub" in claims, "Python JWT missing 'sub'"
    assert "email" in claims, "Python JWT missing 'email'"
    assert "wid" in claims, "Python JWT missing 'wid'"

    # Rust reads sub as string then parses — Python sends int, Rust should handle it
    sub = claims["sub"]
    if isinstance(sub, int):
        str(sub)  # Rust will do user_id.to_string()
    elif isinstance(sub, str):
        int(sub)  # Must be parseable

    print(f"✓ Python JWT claims compatible with Rust schema: {list(claims.keys())}")


# ── Cross-service token acceptance ──────────────────────────────────────────


def test_rust_token_accepted_by_python(client: httpx.Client):
    """Token issued by Rust must be accepted by Python /api/v2/auth/me."""
    email = unique_email("rust-to-py")
    password = "Password123!"

    # Register + signin via Rust (post-#350)
    register = client.post(
        f"{RUST_URL}/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Cross Token",
            "workspace_name": "WS",
        },
    )
    assert register.status_code == 201, f"Rust register failed: {register.text}"
    signin = client.post(
        f"{RUST_URL}/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert signin.status_code == 200, f"Rust signin failed: {signin.text}"
    rust_token = signin.json()["access_token"]

    # Use Rust token on Python /api/v2/auth/me
    me_resp = client.get(
        f"{PYTHON_URL}/api/v2/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"},
    )

    if me_resp.status_code == 200:
        body = me_resp.json()
        # /me wraps its payload in a top-level `data` object
        assert body.get("data", {}).get("email") == email, "Python /me must return same email as Rust token"
        print("✓ Rust-issued JWT accepted by Python")
    else:
        pytest.fail(
            f"Python rejected Rust-issued JWT: {me_resp.status_code} {me_resp.text}. "
            f"Check AUTH_JWT_SECRET is shared between services."
        )


def test_python_token_accepted_by_rust(client: httpx.Client):
    """Token issued by Python must be accepted by Rust /api/v2/me."""
    email = unique_email("py-to-rust")
    password = "Password123!"

    # Register via Python, then login to get a token (post-#350)
    register = client.post(
        f"{PYTHON_URL}/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Py To Rust",
            "workspace_name": "WS",
        },
    )
    assert register.status_code in (200, 201), f"Python register failed: {register.text}"
    login = client.post(
        f"{PYTHON_URL}/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Python login failed: {login.text}"
    python_token = login.json()["access_token"]

    # Use Python token on Rust /api/v2/me
    me_resp = client.get(
        f"{RUST_URL}/api/v2/me",
        headers={"Authorization": f"Bearer {python_token}"},
    )

    if me_resp.status_code == 200:
        body = me_resp.json()
        # /me wraps its payload in a top-level `data` object
        assert body.get("data", {}).get("email") == email, "Rust /me must return same email as Python token"
        print("✓ Python-issued JWT accepted by Rust")
    else:
        pytest.fail(
            f"Rust rejected Python-issued JWT: {me_resp.status_code} {me_resp.text}. "
            f"Check AUTH_JWT_SECRET is shared between services."
        )


# ── Token forgery rejection ─────────────────────────────────────────────────


def test_forged_token_rejected_by_rust(client: httpx.Client):
    """Rust must reject tokens signed with wrong secret."""
    forged = jwt.encode(
        {"sub": "1", "email": "hacker@evil.com", "role": "superadmin", "wid": 1, "exp": 9999999999},
        "wrong-secret",
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get(
        f"{RUST_URL}/api/v2/me",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert resp.status_code == 401, f"Rust must reject forged token, got {resp.status_code}"


def test_forged_token_rejected_by_python(client: httpx.Client):
    """Python must reject tokens signed with wrong secret."""
    forged = jwt.encode(
        {"sub": 1, "email": "hacker@evil.com", "role": "superadmin", "wid": 1, "exp": 9999999999},
        "wrong-secret",
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get(
        f"{PYTHON_URL}/api/v2/auth/me",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert resp.status_code == 401, f"Python must reject forged token, got {resp.status_code}"


def test_none_algorithm_rejected(client: httpx.Client):
    """Both services must reject 'none' algorithm tokens."""
    # PyJWT raises on 'none' by default, but test anyway
    try:
        forged = jwt.encode(
            {"sub": "1", "email": "hacker@evil.com", "role": "superadmin", "wid": 1},
            "",
            algorithm="none",
        )
    except Exception:
        pytest.skip("PyJWT refuses to encode 'none' algorithm — good")

    for url, label in [(RUST_URL, "Rust"), (PYTHON_URL, "Python")]:
        me_path = "/api/v2/me" if label == "Rust" else "/api/v2/auth/me"
        resp = client.get(
            f"{url}{me_path}",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert resp.status_code == 401, f"{label} must reject 'none' algorithm token"
