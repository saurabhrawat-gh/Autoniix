# Post-Harness Implementation Tasks

**Status:** Pending — Execute after HARNESS-ENGINEERING-PLAN.md Week 1-4 completion  
**Created:** 2026-06-20  
**Context:** DB realignment complete (Section 13). Harness implementation in progress.

---

## Phase 1: Build Verification & Schema Compatibility Testing

### 1.1 Rust Gateway Build Verification
**Priority:** Critical  
**Estimated Time:** 30 minutes  
**Prerequisites:** Rust toolchain (1.75+), PostgreSQL test database

```bash
cd /Users/saurabhrawat/Desktop/projects/Autoniix/rust/gateway

# Verify compilation
cargo check

# Run linter
cargo clippy --all-targets --all-features

# Format check
cargo fmt --check

# Run existing tests (requires test DB)
cargo test
```

**Expected Outcome:**
- ✅ Zero compilation errors
- ✅ Zero clippy warnings (or document accepted warnings)
- ✅ All existing tests pass

**Blockers to Resolve:**
- Missing dependencies in Cargo.toml (if any)
- Type mismatches from i64 migration
- SQL query errors (column name mismatches)

---

### 1.2 Test Database Setup
**Priority:** Critical  
**Estimated Time:** 1 hour

**Create:** `rust/gateway/scripts/setup_test_db.sh`
```bash
#!/bin/bash
set -e

DB_NAME="autoniix_test"
DB_USER="${POSTGRES_USER:-postgres}"

echo "Setting up test database: $DB_NAME"

# Drop and recreate test database
psql -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql -U $DB_USER -c "CREATE DATABASE $DB_NAME;"

# Run Python's migrations (schema owner)
echo "Running Python migrations..."
cd ../../src
export DATABASE_URL="postgresql://$DB_USER@localhost/$DB_NAME"

# Apply all Python migrations
# TODO: Replace with actual Python migration command
# Example: alembic upgrade head
# Or: python scripts/run_migrations.py

echo "Test database ready at: postgresql://localhost/$DB_NAME"
```

**Update:** `rust/gateway/.env.test`
```bash
TEST_DATABASE_URL=postgresql://localhost/autoniix_test
AUTH_JWT_SECRET=test-jwt-secret-for-integration-tests-only
```

**Update:** `rust/gateway/src/lib.rs` (test setup)
```rust
#[cfg(test)]
pub async fn create_test_app() -> Router {
    use sqlx::postgres::PgPoolOptions;
    
    dotenvy::from_filename(".env.test").ok();
    
    let database_url = std::env::var("TEST_DATABASE_URL")
        .expect("TEST_DATABASE_URL must be set. Run scripts/setup_test_db.sh first.");
    
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("Failed to connect to test database");
    
    let jwt_secret = std::env::var("AUTH_JWT_SECRET")
        .unwrap_or_else(|_| "test-jwt-secret-key".to_string());
    
    create_app(pool, jwt_secret).await
}
```

---

### 1.3 Schema Compatibility Test Suite
**Priority:** Critical  
**Estimated Time:** 3 hours  
**File:** `rust/gateway/tests/schema_compatibility_test.rs`

```rust
//! Schema compatibility tests per HARNESS-ENGINEERING-PLAN.md Section 13
//! Verifies Rust gateway can read/write Python's production schema.

use serde_json::json;
use sqlx::PgPool;

async fn get_test_pool() -> PgPool {
    let database_url = std::env::var("TEST_DATABASE_URL")
        .expect("TEST_DATABASE_URL must be set");
    sqlx::PgPool::connect(&database_url).await.unwrap()
}

#[tokio::test]
async fn test_rust_reads_python_created_user() {
    // Simulate Python creating a user (direct SQL insert)
    let pool = get_test_pool().await;
    
    let user_id: i64 = sqlx::query_scalar(
        "INSERT INTO users (email, password_hash, display_name, role, disabled, email_verified)
         VALUES ($1, $2, $3, $4, false, true)
         RETURNING id"
    )
    .bind("python-user@example.com")
    .bind("$argon2id$v=19$m=19456,t=2,p=1$...")  // Python's hash
    .bind("Python User")
    .bind("user")
    .fetch_one(&pool)
    .await
    .unwrap();
    
    // Rust gateway reads the same user
    let app = gateway::create_test_app().await;
    // ... (use app to call /api/v2/me with a token for this user)
    
    // Assert: Rust can read Python-created user with i64 id
    assert!(user_id > 0);
}

#[tokio::test]
async fn test_rust_created_user_readable_by_python() {
    // Rust creates user via /api/v2/auth/signup
    let app = gateway::create_test_app().await;
    
    let signup_body = json!({
        "email": "rust-user@example.com",
        "password": "securepassword123",
        "display_name": "Rust User",
        "workspace_name": "Rust Workspace"
    });
    
    // ... (POST to /api/v2/auth/signup)
    
    // Python reads the user (direct SQL query)
    let pool = get_test_pool().await;
    let user: (i64, String, String) = sqlx::query_as(
        "SELECT id, email, display_name FROM users WHERE email = $1"
    )
    .bind("rust-user@example.com")
    .fetch_one(&pool)
    .await
    .unwrap();
    
    assert_eq!(user.1, "rust-user@example.com");
    assert_eq!(user.2, "Rust User");
}

#[tokio::test]
async fn test_rust_jwt_decodes_in_python() {
    // Rust signs in → generates JWT
    let app = gateway::create_test_app().await;
    // ... (POST to /api/v2/auth/signin, get access_token)
    
    // Simulate Python decoding the token
    use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
    
    let token = "...";  // From Rust sign-in response
    let secret = std::env::var("AUTH_JWT_SECRET").unwrap();
    
    let token_data = decode::<serde_json::Value>(
        token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &Validation::new(Algorithm::HS256),
    )
    .unwrap();
    
    let claims = token_data.claims;
    
    // Python parses sub as int
    let user_id: i64 = claims["sub"].as_str().unwrap().parse().unwrap();
    assert!(user_id > 0);
    
    // Python reads wid as int
    let workspace_id: i64 = claims["wid"].as_i64().unwrap();
    assert!(workspace_id > 0);
    
    // Python reads role as string
    assert_eq!(claims["role"].as_str().unwrap(), "owner");
    assert_eq!(claims["global_role"].as_str().unwrap(), "superadmin");
}

#[tokio::test]
async fn test_python_jwt_decodes_in_rust() {
    // Simulate Python creating a JWT
    use jsonwebtoken::{encode, EncodingKey, Header};
    
    let secret = std::env::var("AUTH_JWT_SECRET").unwrap();
    let claims = json!({
        "sub": "42",              // Python stringifies int
        "email": "py@example.com",
        "role": "member",
        "global_role": "user",
        "wid": 7,
        "iat": 1718901234,
        "exp": 1718904834
    });
    
    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .unwrap();
    
    // Rust gateway verifies the token
    let app = gateway::create_test_app().await;
    // ... (GET /api/v2/me with Authorization: Bearer {token})
    
    // Assert: Rust can decode Python-shaped token
}

#[tokio::test]
async fn test_refresh_token_rotation() {
    let app = gateway::create_test_app().await;
    let pool = get_test_pool().await;
    
    // Rust creates session via sign-in
    // ... (POST /api/v2/auth/signin, get refresh_token)
    
    let refresh_token = "...";
    
    // Verify session exists in DB
    let session_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM sessions WHERE user_id = $1 AND revoked_at IS NULL"
    )
    .bind(1)  // user_id from sign-in
    .fetch_one(&pool)
    .await
    .unwrap();
    
    assert_eq!(session_count, 1);
    
    // Rust rotates token via /api/v2/auth/refresh
    // ... (POST /api/v2/auth/refresh with refresh_token)
    
    // Verify old session is rotated, new session exists
    let rotated_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM sessions WHERE user_id = $1 AND rotated_at IS NOT NULL"
    )
    .bind(1)
    .fetch_one(&pool)
    .await
    .unwrap();
    
    assert_eq!(rotated_count, 1);
    
    let active_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM sessions WHERE user_id = $1 AND revoked_at IS NULL AND rotated_at IS NULL"
    )
    .bind(1)
    .fetch_one(&pool)
    .await
    .unwrap();
    
    assert_eq!(active_count, 1);
}

#[tokio::test]
async fn test_workspace_members_role_resolution() {
    let pool = get_test_pool().await;
    
    // Create user + workspace + membership (Python-style)
    let user_id: i64 = sqlx::query_scalar(
        "INSERT INTO users (email, password_hash, role, disabled, email_verified)
         VALUES ($1, $2, $3, false, true) RETURNING id"
    )
    .bind("member@example.com")
    .bind("hash")
    .bind("user")
    .fetch_one(&pool)
    .await
    .unwrap();
    
    let workspace_id: i64 = sqlx::query_scalar(
        "INSERT INTO workspaces (name, slug, plan, mode, owner_user_id)
         VALUES ($1, $2, $3, $4, $5) RETURNING id"
    )
    .bind("Test Workspace")
    .bind("test-workspace")
    .bind("starter")
    .bind("solo")
    .bind(user_id)
    .fetch_one(&pool)
    .await
    .unwrap();
    
    sqlx::query(
        "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ($1, $2, $3)"
    )
    .bind(workspace_id)
    .bind(user_id)
    .bind("viewer")
    .execute(&pool)
    .await
    .unwrap();
    
    // Rust reads workspace role
    use gateway::auth::User;
    let role = User::get_workspace_role(&pool, user_id, workspace_id)
        .await
        .unwrap();
    
    assert_eq!(role, Some("viewer".to_string()));
}

#[tokio::test]
async fn test_logout_revokes_session() {
    let app = gateway::create_test_app().await;
    let pool = get_test_pool().await;
    
    // Sign in → get refresh token
    // ... (POST /api/v2/auth/signin)
    
    let refresh_token = "...";
    
    // Logout
    // ... (POST /api/v2/auth/logout with refresh_token)
    
    // Verify session is revoked
    let revoked_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM sessions WHERE user_id = $1 AND revoked_at IS NOT NULL"
    )
    .bind(1)
    .fetch_one(&pool)
    .await
    .unwrap();
    
    assert_eq!(revoked_count, 1);
}
```

**Run Tests:**
```bash
./scripts/setup_test_db.sh
cargo test --test schema_compatibility_test
```

---

## Phase 2: Integration Testing (Post-Harness)

### 2.1 Dual-Service Integration Test
**Priority:** High  
**Estimated Time:** 4 hours  
**File:** `tests/integration/dual_service_test.py`

```python
"""
Integration tests for Rust gateway + Python dashboard interoperability.
Requires both services running against the same test database.
"""

import pytest
import requests
import jwt
import os

PYTHON_BASE = "http://localhost:8000"  # Python dashboard
RUST_BASE = "http://localhost:8080"    # Rust gateway
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "test-jwt-secret")

@pytest.fixture
def test_db():
    """Reset test database before each test."""
    # Run migrations, clear data, etc.
    pass

def test_python_signup_rust_signin(test_db):
    """User signs up via Python, signs in via Rust."""
    # Python signup
    py_resp = requests.post(f"{PYTHON_BASE}/auth/register", json={
        "email": "cross@example.com",
        "password": "password123",
        "display_name": "Cross User",
        "workspace_name": "Cross Workspace"
    })
    assert py_resp.status_code == 200
    py_data = py_resp.json()
    
    # Rust sign-in (same credentials)
    rust_resp = requests.post(f"{RUST_BASE}/api/v2/auth/signin", json={
        "email": "cross@example.com",
        "password": "password123"
    })
    assert rust_resp.status_code == 200
    rust_data = rust_resp.json()
    
    # Verify JWT compatibility
    py_claims = jwt.decode(py_data["access_token"], JWT_SECRET, algorithms=["HS256"])
    rust_claims = jwt.decode(rust_data["access_token"], JWT_SECRET, algorithms=["HS256"])
    
    assert py_claims["sub"] == rust_claims["sub"]
    assert py_claims["wid"] == rust_claims["wid"]
    assert py_claims["email"] == rust_claims["email"]

def test_rust_signup_python_signin(test_db):
    """User signs up via Rust, signs in via Python."""
    # Rust signup
    rust_resp = requests.post(f"{RUST_BASE}/api/v2/auth/signup", json={
        "email": "rust-first@example.com",
        "password": "password123",
        "display_name": "Rust First",
        "workspace_name": "Rust Workspace"
    })
    assert rust_resp.status_code == 201
    
    # Python sign-in
    py_resp = requests.post(f"{PYTHON_BASE}/auth/login", json={
        "email": "rust-first@example.com",
        "password": "password123"
    })
    assert py_resp.status_code == 200

def test_refresh_token_cross_service(test_db):
    """Refresh token created by Rust, validated by Python (and vice versa)."""
    # Rust sign-in → get refresh token
    rust_resp = requests.post(f"{RUST_BASE}/api/v2/auth/signin", json={
        "email": "refresh@example.com",
        "password": "password123"
    })
    refresh_token = rust_resp.json()["refresh_token"]
    
    # Python refresh endpoint (if it accepts opaque tokens)
    # Note: Python's refresh endpoint needs to read sessions table
    py_refresh = requests.post(f"{PYTHON_BASE}/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert py_refresh.status_code == 200

def test_me_endpoint_cross_service(test_db):
    """Token from Rust works on Python's /me, and vice versa."""
    # Rust sign-in
    rust_resp = requests.post(f"{RUST_BASE}/api/v2/auth/signin", json={
        "email": "me@example.com",
        "password": "password123"
    })
    rust_token = rust_resp.json()["access_token"]
    
    # Python /me endpoint with Rust token
    py_me = requests.get(
        f"{PYTHON_BASE}/auth/me",
        headers={"Authorization": f"Bearer {rust_token}"}
    )
    assert py_me.status_code == 200
    
    # Rust /me endpoint with Python token
    # (Sign in via Python first, get token, call Rust /me)
```

**Setup:**
```bash
# Terminal 1: Python dashboard
cd src/services/dashboard
uvicorn main:app --port 8000

# Terminal 2: Rust gateway
cd rust/gateway
cargo run --release -- --port 8080

# Terminal 3: Run integration tests
pytest tests/integration/dual_service_test.py -v
```

---

### 2.2 Database State Verification
**Priority:** Medium  
**Estimated Time:** 2 hours  
**File:** `tests/integration/db_state_test.py`

```python
"""
Verify database state after Rust operations matches Python's expectations.
"""

import psycopg2
import requests

def test_rust_signup_creates_correct_schema():
    """Rust signup creates all required rows in correct tables."""
    # Rust signup
    resp = requests.post("http://localhost:8080/api/v2/auth/signup", json={
        "email": "db-test@example.com",
        "password": "password123",
        "display_name": "DB Test",
        "workspace_name": "DB Test Workspace"
    })
    user_id = resp.json()["user"]["id"]
    workspace_id = resp.json()["workspace"]["id"]
    
    # Verify database state
    conn = psycopg2.connect("postgresql://localhost/autoniix_test")
    cur = conn.cursor()
    
    # User exists with correct fields
    cur.execute("SELECT id, email, display_name, role, disabled FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    assert user[1] == "db-test@example.com"
    assert user[2] == "DB Test"
    assert user[3] == "superadmin"  # First user
    assert user[4] is False
    
    # Workspace exists
    cur.execute("SELECT id, name, slug, owner_user_id FROM workspaces WHERE id = %s", (workspace_id,))
    workspace = cur.fetchone()
    assert workspace[1] == "DB Test Workspace"
    assert workspace[2] == "db-test-workspace"
    assert workspace[3] == user_id
    
    # Workspace member exists
    cur.execute("SELECT role FROM workspace_members WHERE workspace_id = %s AND user_id = %s", (workspace_id, user_id))
    member = cur.fetchone()
    assert member[0] == "owner"
    
    # Session exists
    cur.execute("SELECT COUNT(*) FROM sessions WHERE user_id = %s AND revoked_at IS NULL", (user_id,))
    session_count = cur.fetchone()[0]
    assert session_count == 1
    
    conn.close()
```

---

## Phase 3: Performance & Load Testing

### 3.1 Benchmark Rust vs Python Auth Endpoints
**Priority:** Medium  
**Estimated Time:** 3 hours  
**Tool:** Apache Bench, wrk, or k6

```bash
# Benchmark Python signup
ab -n 1000 -c 10 -p signup.json -T application/json \
   http://localhost:8000/auth/register

# Benchmark Rust signup
ab -n 1000 -c 10 -p signup.json -T application/json \
   http://localhost:8080/api/v2/auth/signup

# Compare p50, p95, p99 latencies
```

**Create:** `tests/performance/auth_benchmark.js` (k6)
```javascript
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
};

export default function () {
  const payload = JSON.stringify({
    email: `user-${__VU}-${__ITER}@example.com`,
    password: 'password123',
    display_name: 'Load Test User',
    workspace_name: 'Load Test Workspace',
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  // Test Rust gateway
  const rust_resp = http.post('http://localhost:8080/api/v2/auth/signup', payload, params);
  check(rust_resp, {
    'Rust signup status 201': (r) => r.status === 201,
    'Rust signup < 200ms': (r) => r.timings.duration < 200,
  });
}
```

---

### 3.2 Memory & Resource Profiling
**Priority:** Low  
**Estimated Time:** 2 hours

```bash
# Profile Rust gateway under load
cargo build --release
valgrind --tool=massif ./target/release/gateway

# Compare memory usage: Rust vs Python
# Expected: Rust uses ~10-50MB, Python uses ~200-500MB
```

---

## Phase 4: Staging Deployment

### 4.1 Shadow Mode Deployment
**Priority:** High  
**Estimated Time:** 1 day  
**File:** `docs/runbooks/shadow-mode-deployment.md`

**Steps:**
1. Deploy Rust gateway to staging (separate process, same DB as Python)
2. Configure load balancer to duplicate 100% of auth traffic to Rust (responses discarded)
3. Log divergences between Python and Rust responses
4. Monitor for 24 hours
5. Review divergence logs, fix bugs
6. Repeat until divergence rate < 0.1%

**Metrics to Track:**
- Response time delta (Rust vs Python)
- Error rate delta
- Response body divergence rate
- Memory usage
- CPU usage

---

### 4.2 Canary Deployment (1% Traffic)
**Priority:** High  
**Estimated Time:** 3 days  
**File:** `docs/runbooks/canary-deployment.md`

**Steps:**
1. Route 1% of auth traffic to Rust (live responses)
2. Monitor error rate, p95 latency, business metrics
3. Auto-rollback if error rate > 0.1% or p95 > Python + 10%
4. Soak for 24 hours
5. If stable, increase to 10% → 25% → 50% → 100%

**Rollback Triggers:**
- Error rate > 0.1% for 5 minutes
- p95 latency > Python + 20% for 10 minutes
- 5xx spike > 10/min
- Manual trigger via feature flag

---

## Phase 5: Documentation & Runbooks

### 5.1 Database Migration Rollback Runbook
**Priority:** Medium  
**Estimated Time:** 2 hours  
**File:** `docs/runbooks/db-migration-rollback.md`

**Contents:**
- How to rollback Rust gateway to Python (feature flag disable)
- How to verify database state after rollback
- How to handle in-flight sessions (opaque tokens)
- Emergency contact list

---

### 5.2 Operational Playbooks
**Priority:** Medium  
**Estimated Time:** 3 hours

**Create:**
- `docs/runbooks/rust-gateway-troubleshooting.md`
- `docs/runbooks/auth-service-incidents.md`
- `docs/runbooks/database-schema-changes.md`

---

## Phase 6: Monitoring & Observability

### 6.1 Grafana Dashboards
**Priority:** High  
**Estimated Time:** 4 hours

**Create:** `observability/grafana/rust-gateway-dashboard.json`

**Panels:**
- Request rate (Rust vs Python)
- Error rate (Rust vs Python)
- p50/p95/p99 latency (Rust vs Python)
- Active sessions count
- Token refresh rate
- Database connection pool usage

---

### 6.2 Alerting Rules
**Priority:** High  
**Estimated Time:** 2 hours

**Create:** `observability/prometheus/rust-gateway-alerts.yml`

```yaml
groups:
  - name: rust_gateway
    rules:
      - alert: RustGatewayHighErrorRate
        expr: rate(http_requests_total{service="rust-gateway",status=~"5.."}[5m]) > 0.01
        for: 5m
        annotations:
          summary: "Rust gateway error rate > 1%"
      
      - alert: RustGatewaySlowResponses
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="rust-gateway"}[5m])) > 0.2
        for: 10m
        annotations:
          summary: "Rust gateway p95 latency > 200ms"
```

---

## Phase 7: Production Readiness Checklist

### 7.1 Security Audit
**Priority:** Critical  
**Estimated Time:** 1 day

- [ ] SQL injection vulnerability scan
- [ ] JWT secret rotation procedure documented
- [ ] Rate limiting on auth endpoints
- [ ] OWASP Top 10 compliance check
- [ ] Dependency vulnerability scan (`cargo audit`)

---

### 7.2 Compliance & Legal
**Priority:** High  
**Estimated Time:** 1 day

- [ ] GDPR compliance (user data deletion via Rust)
- [ ] Session expiry aligns with security policy
- [ ] Audit logging for auth events
- [ ] Data retention policy for sessions table

---

## Execution Order (Recommended)

**Week 1-4:** Harness Implementation (current focus)  
**Week 5:**
- Day 1-2: Build verification + schema compatibility tests
- Day 3-4: Dual-service integration tests
- Day 5: Performance benchmarks

**Week 6:**
- Day 1-2: Shadow mode deployment to staging
- Day 3-5: Bug fixes from shadow mode

**Week 7:**
- Day 1-3: Canary deployment (1% → 10% → 25%)
- Day 4-5: Monitoring & alerting setup

**Week 8:**
- Day 1-2: Canary deployment (50% → 100%)
- Day 3-5: Documentation & runbooks

**Week 9:**
- Production rollout
- Post-deployment monitoring

---

## Success Criteria

Before marking this document complete:
- ✅ All schema compatibility tests pass
- ✅ Integration tests pass (Python ↔ Rust interoperability)
- ✅ Performance benchmarks show Rust ≥ Python (latency, throughput)
- ✅ Shadow mode runs 24h with divergence rate < 0.1%
- ✅ Canary deployment reaches 100% with zero incidents
- ✅ Monitoring dashboards live in production
- ✅ Runbooks reviewed by ops team
- ✅ Security audit complete

---

## Notes

- This document assumes HARNESS-ENGINEERING-PLAN.md Week 1-4 is complete
- All tasks are blocked until harness implementation finishes
- Update this document as new requirements emerge during harness work
- Estimated times are for a single engineer; adjust for team size
