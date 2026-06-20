"""
Database schema compatibility tests — verify Rust and Python can read each other's data.

Per HARNESS-ENGINEERING-PLAN.md Section 13.

Requires both services running against the same database.
Skip automatically if services or DB are not available.

Run:
    PYTHON_DASHBOARD_URL=http://localhost:8000 \
    RUST_GATEWAY_URL=http://localhost:8080 \
    TEST_DATABASE_URL=postgresql://localhost/autoniix_test \
    pytest tests/migration/test_schema_compatibility.py -v
"""
from __future__ import annotations

import os
import time

import httpx
import psycopg2
import pytest

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/autoniix_test")


def unique_email(label: str = "schema") -> str:
    return f"{label}-{int(time.time() * 1_000_000)}@schema.test"


@pytest.fixture
def client():
    with httpx.Client(timeout=15.0) as c:
        yield c


@pytest.fixture
def db():
    try:
        conn = psycopg2.connect(DB_URL)
    except psycopg2.OperationalError:
        pytest.skip(f"Cannot connect to test database at {DB_URL}")
    yield conn
    conn.close()


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


@pytest.fixture(autouse=True)
def _check_services(client: httpx.Client):
    skip_if_unavailable(client, PYTHON_URL, "Python dashboard")
    skip_if_unavailable(client, RUST_URL, "Rust gateway")


# ── Rust reads Python-created data ──────────────────────────────────────────


def test_rust_reads_python_created_user(client: httpx.Client):
    """User created via Python must be readable by Rust (signin)."""
    email = unique_email("py-to-rust")
    password = "Password123!"

    # Create user via Python
    resp = client.post(
        f"{PYTHON_URL}/auth/register",
        json={"email": email, "password": password, "workspace_name": "Schema WS"},
    )
    assert resp.status_code in (200, 201), f"Python register failed: {resp.text}"

    # Rust must be able to sign in with same credentials
    signin = client.post(
        f"{RUST_URL}/api/v2/auth/signin",
        json={"email": email, "password": password},
    )
    assert signin.status_code == 200, (
        f"Rust signin failed for Python-created user: {signin.text}"
    )
    assert signin.json().get("access_token"), "Rust must return access_token"


def test_rust_reads_python_created_user_from_db(db):
    """Verify Python-created user row has integer id (not UUID) in DB."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, email FROM users WHERE email LIKE '%@schema.test' ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row is None:
        pytest.skip("No schema.test users in DB — run with data")

    user_id, email = row
    assert isinstance(user_id, int), f"User id must be integer, got {type(user_id)}"
    assert user_id > 0, "User id must be positive"
    cursor.close()


# ── Python reads Rust-created data ──────────────────────────────────────────


def test_python_reads_rust_created_user(client: httpx.Client):
    """User created via Rust must be readable by Python (login)."""
    email = unique_email("rust-to-py")
    password = "Password123!"

    # Create user via Rust
    resp = client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "Schema WS"},
    )
    assert resp.status_code == 201, f"Rust signup failed: {resp.text}"

    # Python must be able to log in with same credentials
    login = client.post(
        f"{PYTHON_URL}/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, (
        f"Python login failed for Rust-created user: {login.text}"
    )
    assert login.json().get("access_token"), "Python must return access_token"


def test_rust_signup_creates_correct_db_rows(client: httpx.Client, db):
    """Rust signup must create rows in users, workspaces, workspace_members, sessions."""
    email = unique_email("db-rows")
    password = "Password123!"

    resp = client.post(
        f"{RUST_URL}/api/v2/auth/signup",
        json={"email": email, "password": password, "workspace_name": "DB Rows WS"},
    )
    assert resp.status_code == 201, f"Rust signup failed: {resp.text}"

    body = resp.json()
    user_id = body.get("user", {}).get("id")
    workspace_id = body.get("workspace", {}).get("id")

    cursor = db.cursor()

    # Check user row
    cursor.execute("SELECT id, email, role, disabled FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    assert user is not None, f"User row not found for id={user_id}"
    assert user[1] == email, f"User email mismatch: {user[1]} vs {email}"
    assert isinstance(user[0], int), "User id must be integer"
    assert user[3] is False, "User must not be disabled"

    # Check workspace row
    cursor.execute("SELECT id, name, owner_user_id FROM workspaces WHERE id = %s", (workspace_id,))
    ws = cursor.fetchone()
    assert ws is not None, f"Workspace row not found for id={workspace_id}"
    assert ws[2] == user_id, "Workspace owner must match user id"

    # Check workspace_members row
    cursor.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
        (workspace_id, user_id),
    )
    member = cursor.fetchone()
    assert member is not None, "workspace_members row not found"
    assert member[0] == "owner", f"First user must be 'owner', got '{member[0]}'"

    # Check session row
    cursor.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )
    session_count = cursor.fetchone()[0]
    assert session_count >= 1, "At least one active session must exist"

    cursor.close()


# ── Schema structure validation ─────────────────────────────────────────────


def test_users_table_uses_integer_ids(db):
    """Users table must use SERIAL integer ids, not UUIDs."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'id'"
    )
    row = cursor.fetchone()
    assert row is not None, "users.id column not found"
    assert row[1] in ("integer", "bigint"), (
        f"users.id must be integer type, got {row[1]}"
    )
    cursor.close()


def test_workspaces_table_uses_integer_ids(db):
    """Workspaces table must use SERIAL integer ids."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'workspaces' AND column_name = 'id'"
    )
    row = cursor.fetchone()
    assert row is not None, "workspaces.id column not found"
    assert row[1] in ("integer", "bigint"), (
        f"workspaces.id must be integer type, got {row[1]}"
    )
    cursor.close()


def test_workspace_members_table_exists(db):
    """workspace_members table must exist (not user_roles)."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'workspace_members')"
    )
    assert cursor.fetchone()[0], "workspace_members table must exist"
    cursor.close()


def test_sessions_table_exists(db):
    """sessions table must exist for opaque refresh tokens."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sessions')"
    )
    assert cursor.fetchone()[0], "sessions table must exist"
    cursor.close()


def test_user_roles_table_does_not_exist(db):
    """user_roles table must NOT exist (replaced by workspace_members)."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_roles')"
    )
    assert not cursor.fetchone()[0], "user_roles table must not exist (use workspace_members)"
    cursor.close()
