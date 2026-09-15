# Rust Gateway Troubleshooting Runbook

**Status:** Active  
**Last Updated:** 2026-06-20

---

## Common Issues

### 1. Gateway Won't Start

**Symptom:** `cargo run` fails or container exits immediately

**Diagnosis:**

```bash
# Check logs
docker compose logs rust-gateway --tail=100

# Common causes:
# - Missing AUTH_JWT_SECRET env var
# - Cannot connect to PostgreSQL
# - Port 8080 already in use
```

**Fix:**

```bash
# Ensure .env has required vars
grep AUTH_JWT_SECRET .env
grep DATABASE_URL .env

# Check PostgreSQL is running
docker compose ps postgres-app

# Check port availability
lsof -i :8080
```

### 2. JWT Token Rejected by Python

**Symptom:** Rust-issued tokens return 401 on Python endpoints

**Diagnosis:**

```bash
# Verify shared secret
echo "Rust: $(grep AUTH_JWT_SECRET rust/gateway/.env)"
echo "Python: $(grep AUTH_JWT_SECRET .env)"

# Decode a token
echo "eyJ..." | jwt decode -s $(grep AUTH_JWT_SECRET .env | cut -d= -f2)
```

**Fix:** Ensure both services use the exact same `AUTH_JWT_SECRET` value.

### 3. Database Schema Mismatch

**Symptom:** Rust gateway returns 500 on auth endpoints

**Diagnosis:**

```bash
# Run schema compatibility tests
TEST_DATABASE_URL=postgresql://localhost/autoniix_test \
  cargo test -p gateway --test schema_compatibility_test

# Check for user_roles table (should NOT exist)
docker compose exec -T postgres-app psql -U app -d autoniix -c \
  "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_roles')"
```

**Fix:**

- Rust must use integer-keyed schema (users.id is `i64`, not UUID)
- Workspace roles read from `workspace_members`, not `user_roles`
- Refresh tokens stored in `sessions` table (opaque, not JWT)

### 4. High Latency

**Symptom:** p95 latency > 200ms on auth endpoints

**Diagnosis:**

```bash
# Check Prometheus metrics
curl http://localhost:8080/metrics | grep http_request_duration

# Check DB connection pool
curl http://localhost:8080/metrics | grep sqlx_pool
```

**Fix:**

- Increase `max_connections` in pool config
- Check for slow queries: `SELECT * FROM pg_stat_activity WHERE state = 'active'`
- Run Criterion benchmarks: `cargo bench -p gateway`

### 5. Equivalence Test Failures

**Symptom:** `cargo test -p harness equivalence` fails

**Diagnosis:**

```bash
# Run with verbose output
RUST_GATEWAY_URL=http://localhost:8080 \
PYTHON_DASHBOARD_URL=http://localhost:8000 \
cargo test -p harness equivalence -- --nocapture
```

**Fix:**

- Check divergence registry for intentional differences
- Verify both services are running and healthy
- Compare response bodies manually

---

## Health Check Endpoints

| Service          | Endpoint      | Expected            |
| ---------------- | ------------- | ------------------- |
| Rust Gateway     | `GET /health` | 200 OK              |
| Python Dashboard | `GET /health` | 200 OK              |
| PostgreSQL       | `pg_isready`  | accepts connections |

---

## Log Locations

| Component        | Location                            |
| ---------------- | ----------------------------------- |
| Rust Gateway     | `docker compose logs rust-gateway`  |
| Python Dashboard | `docker compose logs dashboard-bff` |
| PostgreSQL       | `docker compose logs postgres-app`  |
| Traefik          | `docker compose logs traefik`       |
