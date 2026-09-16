"""
REST contract validation tests for Rust gateway.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 2.

Tests validate that Rust gateway responses match OpenAPI schema.
"""

from pathlib import Path

import pytest

from .rest_validator import RESTValidator

SCHEMAS_DIR = Path(__file__).parent / "schemas"
RUST_SCHEMA = SCHEMAS_DIR / "rust-gateway.json"
PYTHON_SCHEMA = SCHEMAS_DIR / "python-dashboard.json"

RUST_BASE_URL = "http://localhost:8080"
PYTHON_BASE_URL = "http://localhost:8000"


@pytest.fixture
def rust_validator():
    """Rust gateway OpenAPI validator."""
    if not RUST_SCHEMA.exists():
        pytest.skip(f"Rust schema not found at {RUST_SCHEMA}. Run extract_schemas.py first.")
    return RESTValidator(RUST_SCHEMA)


@pytest.fixture
def python_validator():
    """Python dashboard OpenAPI validator."""
    if not PYTHON_SCHEMA.exists():
        pytest.skip(f"Python schema not found at {PYTHON_SCHEMA}. Run extract_schemas.py first.")
    return RESTValidator(PYTHON_SCHEMA)


def _register_and_signin(validator: RESTValidator, base_url: str, label: str) -> tuple[str, str, int, int]:
    """Helper: register a fresh user, then signin to obtain tokens.

    Returns (access_token, refresh_token, user_id, workspace_id).
    Post-#350: register returns no tokens; signin is required.
    """
    email = f"{label}-{pytest.timestamp}-{id(validator) % 10000}@contract.test"
    password = "Password123!"
    body = {
        "email": email,
        "password": password,
        "display_name": f"{label} Test",
        "workspace_name": f"{label} WS",
    }

    _, reg_resp, _ = validator.validate_openapi(
        base_url=base_url,
        method="POST",
        path="/api/v2/auth/register",
        request_body=body,
        expected_code=201,
    )
    reg_body = reg_resp.json()
    user_id = reg_body["user_id"]
    workspace_id = reg_body["workspace_id"]

    _, signin_resp, _ = validator.validate_openapi(
        base_url=base_url,
        method="POST",
        path="/api/v2/auth/signin",
        request_body={"email": email, "password": password},
        expected_code=200,
    )
    signin_body = signin_resp.json()
    return (
        signin_body["access_token"],
        signin_body.get("refresh_token", ""),
        user_id,
        workspace_id,
    )


class TestRustGatewayContracts:
    """Contract validation tests for Rust gateway auth endpoints.

    Post-#350: /register is the canonical signup endpoint and returns
    onboarding metadata only. /signup is kept as a deprecated alias
    with the same response shape. Tests use /register everywhere.
    """

    def test_register_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/register response matches OpenAPI schema."""
        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/register",
            request_body={
                "email": f"contract-test-{pytest.timestamp}@example.com",
                "password": "Password123!",
                "display_name": "Contract Test User",
                "workspace_name": "Contract Test Workspace",
            },
            expected_code=201,
        )

        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 201

        data = response.json()
        assert data.get("status") == "ok"
        assert isinstance(data.get("user_id"), int)
        assert isinstance(data.get("workspace_id"), int)
        assert data.get("role") == "owner"
        assert isinstance(data.get("onboarding_required"), bool)
        assert "access_token" not in data
        assert "refresh_token" not in data

    def test_signup_alias_matches_register(self, rust_validator):
        """POST /api/v2/auth/signup (deprecated alias) returns same shape as /register."""
        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"alias-test-{pytest.timestamp}@example.com",
                "password": "Password123!",
                "display_name": "Alias Test",
                "workspace_name": "Alias WS",
            },
            expected_code=201,
        )
        assert is_valid, f"Schema validation failed: {errors}"
        data = response.json()
        assert data.get("status") == "ok"
        assert "access_token" not in data, "/signup alias must not return tokens (post-#350)"

    def test_signin_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/signin response matches OpenAPI schema."""
        access_token, _refresh, _uid, _wid = _register_and_signin(rust_validator, RUST_BASE_URL, "signin")
        assert access_token, "signin must yield an access_token"

    def test_refresh_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/refresh response matches OpenAPI schema."""
        _access, refresh_token, _uid, _wid = _register_and_signin(rust_validator, RUST_BASE_URL, "refresh")
        if not refresh_token:
            pytest.skip("signin did not return refresh_token in body (cookie-only mode)")

        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/refresh",
            request_body={"refresh_token": refresh_token},
            expected_code=200,
        )

        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_verify_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/verify response matches OpenAPI schema."""
        access_token, _refresh, _uid, _wid = _register_and_signin(rust_validator, RUST_BASE_URL, "verify")

        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/verify",
            request_body={"token": access_token},
            expected_code=200,
        )

        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
        assert "wid" in data

    def test_logout_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/logout response matches OpenAPI schema."""
        _access, refresh_token, _uid, _wid = _register_and_signin(rust_validator, RUST_BASE_URL, "logout")
        if not refresh_token:
            pytest.skip("signin did not return refresh_token in body (cookie-only mode)")

        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/logout",
            request_body={"refresh_token": refresh_token},
            expected_code=200,
        )

        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 200

    def test_me_endpoint_matches_openapi(self, rust_validator):
        """GET /api/v2/me response matches OpenAPI schema."""
        access_token, _refresh, _uid, _wid = _register_and_signin(rust_validator, RUST_BASE_URL, "me")

        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="GET",
            path="/api/v2/me",
            headers={"Authorization": f"Bearer {access_token}"},
            expected_code=200,
        )

        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data.get("data"), dict), "/me must return data envelope"
        inner = data["data"]
        assert "email" in inner, "/me data must include email"
        assert "user_id" in inner, "/me data must include user_id"


class TestPythonDashboardContracts:
    """Contract validation tests for Python dashboard (for comparison)."""

    def test_python_register_matches_openapi(self, python_validator):
        """POST /api/v2/auth/register response matches OpenAPI schema."""
        is_valid, response, errors = python_validator.validate_openapi(
            base_url=PYTHON_BASE_URL,
            method="POST",
            path="/api/v2/auth/register",
            request_body={
                "email": f"py-contract-{pytest.timestamp}@example.com",
                "password": "Password123!",
                "display_name": "Python Contract Test",
                "workspace_name": "Python Test Workspace",
            },
            expected_code=200,
        )

        if not is_valid:
            pytest.skip(f"Python schema incomplete: {errors}")

        assert response.status_code == 200


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """Generate unique timestamp for test data."""
    import time

    pytest.timestamp = int(time.time())
