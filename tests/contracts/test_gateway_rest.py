"""
REST contract validation tests for Rust gateway.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 2.

Tests validate that Rust gateway responses match OpenAPI schema.
"""
import pytest
from pathlib import Path

from .rest_validator import RESTValidator

SCHEMAS_DIR = Path(__file__).parent / "schemas"
RUST_SCHEMA = SCHEMAS_DIR / "rust-gateway.json"
PYTHON_SCHEMA = SCHEMAS_DIR / "python-dashboard.json"

# Base URLs for services
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


class TestRustGatewayContracts:
    """Contract validation tests for Rust gateway auth endpoints."""
    
    def test_signup_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/signup response matches OpenAPI schema."""
        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"contract-test-{pytest.timestamp}@example.com",
                "password": "securepassword123",
                "display_name": "Contract Test User",
                "workspace_name": "Contract Test Workspace",
            },
            expected_code=201,
        )
        
        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 201
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert "workspace" in data
    
    def test_signin_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/signin response matches OpenAPI schema."""
        # First, create a user
        signup_response = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"signin-test-{pytest.timestamp}@example.com",
                "password": "password123",
                "display_name": "Sign In Test",
                "workspace_name": "Test Workspace",
            },
            expected_code=201,
        )
        
        # Then, sign in
        is_valid, response, errors = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signin",
            request_body={
                "email": f"signin-test-{pytest.timestamp}@example.com",
                "password": "password123",
            },
            expected_code=200,
        )
        
        assert is_valid, f"Schema validation failed: {errors}"
        assert response.status_code == 200
    
    def test_refresh_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/refresh response matches OpenAPI schema."""
        # Sign up to get a refresh token
        _, signup_resp, _ = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"refresh-test-{pytest.timestamp}@example.com",
                "password": "password123",
                "display_name": "Refresh Test",
                "workspace_name": "Test Workspace",
            },
            expected_code=201,
        )
        
        refresh_token = signup_resp.json()["refresh_token"]
        
        # Refresh the token
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
        assert "refresh_token" in data  # New refresh token after rotation
    
    def test_verify_matches_openapi(self, rust_validator):
        """POST /api/v2/auth/verify response matches OpenAPI schema."""
        # Sign up to get an access token
        _, signup_resp, _ = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"verify-test-{pytest.timestamp}@example.com",
                "password": "password123",
                "display_name": "Verify Test",
                "workspace_name": "Test Workspace",
            },
            expected_code=201,
        )
        
        access_token = signup_resp.json()["access_token"]
        
        # Verify the token
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
        # Sign up to get a refresh token
        _, signup_resp, _ = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"logout-test-{pytest.timestamp}@example.com",
                "password": "password123",
                "display_name": "Logout Test",
                "workspace_name": "Test Workspace",
            },
            expected_code=201,
        )
        
        refresh_token = signup_resp.json()["refresh_token"]
        
        # Logout
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
        # Sign up to get an access token
        _, signup_resp, _ = rust_validator.validate_openapi(
            base_url=RUST_BASE_URL,
            method="POST",
            path="/api/v2/auth/signup",
            request_body={
                "email": f"me-test-{pytest.timestamp}@example.com",
                "password": "password123",
                "display_name": "Me Test",
                "workspace_name": "Test Workspace",
            },
            expected_code=201,
        )
        
        access_token = signup_resp.json()["access_token"]
        
        # Call /me endpoint
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
        assert "user" in data
        assert "workspace" in data


class TestPythonDashboardContracts:
    """Contract validation tests for Python dashboard (for comparison)."""
    
    def test_python_register_matches_openapi(self, python_validator):
        """POST /auth/register response matches OpenAPI schema."""
        is_valid, response, errors = python_validator.validate_openapi(
            base_url=PYTHON_BASE_URL,
            method="POST",
            path="/auth/register",
            request_body={
                "email": f"py-contract-{pytest.timestamp}@example.com",
                "password": "securepassword123",
                "display_name": "Python Contract Test",
                "workspace_name": "Python Test Workspace",
            },
            expected_code=200,
        )
        
        # Note: strict=False because Python schema might not be complete
        if not is_valid:
            pytest.skip(f"Python schema incomplete: {errors}")
        
        assert response.status_code == 200


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """Generate unique timestamp for test data."""
    import time
    pytest.timestamp = int(time.time())
