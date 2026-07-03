"""
OWASP Top 10 security tests for auth endpoints.

Per HARNESS-ENGINEERING-PLAN.md Section 14.

Tests SQL injection, JWT forgery, brute force, and other common attacks
against both Python and Rust auth endpoints.

Run:
    RUST_GATEWAY_URL=http://localhost:8080 \
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    pytest tests/security/test_auth_security.py -v
"""
from __future__ import annotations

import os
import time

import httpx
import jwt
import pytest

RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "test-jwt-secret")
JWT_ALGORITHM = "HS256"


def unique_email(label: str = "sec") -> str:
    return f"{label}-{int(time.time() * 1_000_000)}@sec.test"


@pytest.fixture
def client():
    with httpx.Client(timeout=15.0) as c:
        yield c


def skip_if_unavailable(client: httpx.Client, url: str, label: str) -> None:
    try:
        r = client.get(f"{url}/health", timeout=3.0)
        if "html" in r.headers.get("content-type", ""):
            pytest.skip(f"{label} not running at {url} (got HTML, expected JSON API)")
        r.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"{label} not running at {url}")
    except Exception:
        pytest.skip(f"{label} at {url} did not return valid JSON")


@pytest.fixture
def rust_available(client: httpx.Client):
    skip_if_unavailable(client, RUST_URL, "Rust gateway")


@pytest.fixture
def python_available(client: httpx.Client):
    skip_if_unavailable(client, PYTHON_URL, "Python dashboard")




class TestSQLInjection:
    """OWASP A03:2021 — Injection."""

    @pytest.mark.usefixtures("rust_available")
    def test_sql_injection_in_email_rust(self, client: httpx.Client):
        """SQL injection in email field must not succeed."""
        payloads = [
            "admin'--",
            "admin' OR '1'='1",
            "admin'; DROP TABLE users;--",
            "admin' UNION SELECT * FROM users;--",
            "' OR 1=1 --",
        ]
        for payload in payloads:
            resp = client.post(
                f"{RUST_URL}/api/v2/auth/signin",
                json={"email": payload, "password": "anything"},
            )
            assert resp.status_code in (400, 401, 422), (
                f"Rust must reject SQL injection payload '{payload}', got {resp.status_code}"
            )

    @pytest.mark.usefixtures("python_available")
    def test_sql_injection_in_email_python(self, client: httpx.Client):
        """SQL injection in email field must not succeed on Python."""
        payloads = [
            "admin'--",
            "admin' OR '1'='1",
            "admin'; DROP TABLE users;--",
        ]
        for payload in payloads:
            resp = client.post(
                f"{PYTHON_URL}/api/v2/auth/login",
                json={"email": payload, "password": "anything"},
            )
            assert resp.status_code in (400, 401, 422), (
                f"Python must reject SQL injection payload '{payload}', got {resp.status_code}"
            )

    @pytest.mark.usefixtures("rust_available")
    def test_sql_injection_in_register_email_rust(self, client: httpx.Client):
        """#350 made /register public — verify injection in register email
        is rejected before INSERT, regardless of first-user vs nth-user path."""
        payloads = [
            "admin'); DROP TABLE users;--",
            "x@y.com'; UPDATE users SET role='superadmin' WHERE 1=1;--",
        ]
        for payload in payloads:
            resp = client.post(
                f"{RUST_URL}/api/v2/auth/register",
                json={
                    "email": payload,
                    "password": "Password123!",
                    "display_name": "Injection",
                    "workspace_name": "InjWS",
                },
            )
            assert resp.status_code in (400, 409, 422), (
                f"Rust /register must reject injection payload '{payload}', "
                f"got {resp.status_code}"
            )




class TestJWTSecurity:
    """OWASP A02:2021 — Cryptographic Failures."""

    @pytest.mark.usefixtures("rust_available")
    def test_none_algorithm_rejected_rust(self, client: httpx.Client):
        """Rust must reject JWT with 'none' algorithm."""
        try:
            token = jwt.encode(
                {"sub": "1", "email": "hacker@evil.com", "role": "superadmin", "wid": 1, "exp": 9999999999},
                "",
                algorithm="none",
            )
        except Exception:
            pytest.skip("PyJWT refuses 'none' — good")

        resp = client.get(
            f"{RUST_URL}/api/v2/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401, "Rust must reject 'none' algorithm"

    @pytest.mark.usefixtures("rust_available")
    def test_wrong_secret_rejected_rust(self, client: httpx.Client):
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
        assert resp.status_code == 401, "Rust must reject wrong-secret token"

    @pytest.mark.usefixtures("rust_available")
    def test_expired_token_rejected_rust(self, client: httpx.Client):
        """Rust must reject expired JWT tokens."""
        expired = jwt.encode(
            {"sub": "1", "email": "expired@sec.test", "role": "user", "wid": 1, "exp": 1, "iat": 1},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        resp = client.get(
            f"{RUST_URL}/api/v2/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401, "Rust must reject expired token"

    @pytest.mark.usefixtures("rust_available")
    def test_privilege_escalation_via_jwt_rust(self, client: httpx.Client):
        """Forged JWT with elevated role must not actually grant elevated
        access. The token is technically valid (signed with the right
        secret) but the server MUST read the authoritative role from the
        database, not from the JWT claim, when making authorization
        decisions. Documents the expected behavior so a regression that
        trusts the JWT role is caught."""
        email = unique_email("privesc")
        register = client.post(
            f"{RUST_URL}/api/v2/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "display_name": "Priv Esc",
                "workspace_name": "WS",
            },
        )
        if register.status_code != 201:
            pytest.skip("Cannot create test user via /register")
        user_id = register.json()["user_id"]

        forged = jwt.encode(
            {
                "sub": str(user_id),
                "email": email,
                "role": "superadmin",
                "global_role": "superadmin",
                "wid": register.json()["workspace_id"],
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        resp = client.get(
            f"{RUST_URL}/api/v2/me",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert resp.status_code == 200, (
            f"Token signed with correct secret should be accepted: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        global_role = (body.get("data") or {}).get("global_role") or body.get("global_role")
        assert global_role != "superadmin", (
            f"PRIVILEGE ESCALATION: /me returned global_role='superadmin' from "
            f"forged JWT claim. Server must read role from DB, not JWT."
        )




class TestBruteForce:
    """OWASP A07:2021 — Identification and Authentication Failures."""

    @pytest.mark.usefixtures("rust_available")
    def test_brute_force_rate_limiting_rust(self, client: httpx.Client):
        """Rust should rate-limit repeated failed login attempts. After
        20 wrong-password attempts we expect either a 429 (rate limited)
        or all 401s; a single 200 would mean we either succeeded with
        the wrong password (impossible) or hit a session re-use bug."""
        email = unique_email("brute")
        client.post(
            f"{RUST_URL}/api/v2/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "display_name": "Brute",
                "workspace_name": "WS",
            },
        )

        statuses = []
        for _ in range(20):
            resp = client.post(
                f"{RUST_URL}/api/v2/auth/signin",
                json={"email": email, "password": "WrongPassword!"},
            )
            statuses.append(resp.status_code)

        assert 200 not in statuses, "Must not succeed with wrong password"
        if 429 in statuses:
            print(f"✓ Rate limiting active: got 429 after {statuses.index(429) + 1} attempts")
        else:
            print("⚠ No rate limiting detected — all 20 attempts returned 401 (no 429)")

    @pytest.mark.usefixtures("rust_available")
    def test_timing_attack_resistance_rust(self, client: httpx.Client):
        """Login with wrong password should take similar time regardless of email validity."""
        import time as _time

        start = _time.monotonic()
        client.post(
            f"{RUST_URL}/api/v2/auth/signin",
            json={"email": "nonexistent@sec.test", "password": "wrong"},
        )
        nonexistent_time = _time.monotonic() - start

        email = unique_email("timing")
        client.post(
            f"{RUST_URL}/api/v2/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "display_name": "Timing",
                "workspace_name": "WS",
            },
        )
        start = _time.monotonic()
        client.post(
            f"{RUST_URL}/api/v2/auth/signin",
            json={"email": email, "password": "wrong"},
        )
        existing_time = _time.monotonic() - start

        diff = abs(existing_time - nonexistent_time)
        if diff > 0.5:
            print(
                f"⚠ Timing difference detected: nonexistent={nonexistent_time:.3f}s "
                f"vs existing={existing_time:.3f}s (diff={diff:.3f}s) — "
                f"may allow user enumeration"
            )
        else:
            print(f"✓ Timing attack resistant (diff={diff:.3f}s)")




class TestSecurityHeaders:
    """OWASP A05:2021 — Security Misconfiguration."""

    @pytest.mark.usefixtures("rust_available")
    def test_security_headers_rust(self, client: httpx.Client):
        """Rust gateway should return security headers."""
        resp = client.get(f"{RUST_URL}/health")

        recommended = [
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
        ]
        missing = [h for h in recommended if h not in {k.lower() for k in resp.headers}]
        if missing:
            print(f"⚠ Missing security headers: {missing}")
        else:
            print("✓ All recommended security headers present")




class TestPasswordPolicy:
    """OWASP A08:2021 — Software and Data Integrity Failures (password policy)."""

    @pytest.mark.usefixtures("rust_available")
    def test_weak_password_rejected_rust(self, client: httpx.Client):
        """Rust /register should reject passwords shorter than 8 chars.
        Documents the current policy (Plan §14: "min 8 chars + complexity"
        — we only enforce length so far; complexity is a follow-up)."""
        weak_passwords = ["", "x", "123", "abc", "1234567"]
        for pw in weak_passwords:
            resp = client.post(
                f"{RUST_URL}/api/v2/auth/register",
                json={
                    "email": unique_email("weak"),
                    "password": pw,
                    "display_name": "Weak",
                    "workspace_name": "WS",
                },
            )
            assert resp.status_code in (400, 422), (
                f"Rust /register must reject weak password '{pw}' (len={len(pw)}), "
                f"got {resp.status_code}: {resp.text}"
            )

    @pytest.mark.usefixtures("rust_available")
    def test_long_password_handled_rust(self, client: httpx.Client):
        """Rust should handle very long passwords gracefully (not crash).
        Argon2 has a 4096-byte input limit; the server must validate or
        truncate before hashing, never 500."""
        long_pw = "A" * 10000
        resp = client.post(
            f"{RUST_URL}/api/v2/auth/register",
            json={
                "email": unique_email("longpw"),
                "password": long_pw,
                "display_name": "Long",
                "workspace_name": "WS",
            },
        )
        assert resp.status_code != 500, (
            f"Rust must not crash on long password, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.usefixtures("rust_available")
    def test_duplicate_email_returns_409_rust(self, client: httpx.Client):
        """#350: a second registration with the same email must return 409
        (not 500, not 200). Prevents silent overwrites + user enumeration
        via 200 vs 500 timing differences."""
        email = unique_email("dup")
        body = {
            "email": email,
            "password": "Password123!",
            "display_name": "Dup",
            "workspace_name": "DupWS",
        }

        first = client.post(f"{RUST_URL}/api/v2/auth/register", json=body)
        assert first.status_code == 201, f"first register must succeed: {first.text}"

        second = client.post(f"{RUST_URL}/api/v2/auth/register", json=body)
        assert second.status_code == 409, (
            f"duplicate email must return 409, got {second.status_code}: {second.text}"
        )
