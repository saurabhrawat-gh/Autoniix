# Rust Gateway Rollback Runbook

**Status:** Active  
**Last Updated:** 2026-06-20  
**Applies To:** Python → Rust/Go multi-language backend migration

---

## When to Use This Runbook

- Rust gateway is producing errors after a deployment
- Database schema incompatibility detected
- JWT token validation failures across services
- Equivalence tests failing in production sampling

---

## Rollback Levels

### Level 1: Single Endpoint (Feature Flag)

Use when one endpoint is misbehaving but the rest of the Rust gateway is fine.

```bash
# Disable specific endpoint flag via Unleash/LaunchDarkly UI or API:
curl -X PUT https://unleash.local/api/features/rust_auth_signup \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'
```

**Kill-switch SLA:** Disable any flag in <60 seconds without deploy.

| Flag                | Endpoint                  | Status |
| ------------------- | ------------------------- | ------ |
| `rust_auth_signup`  | POST /api/v2/auth/signup  | Active |
| `rust_auth_signin`  | POST /api/v2/auth/signin  | Active |
| `rust_auth_refresh` | POST /api/v2/auth/refresh | Active |
| `rust_auth_me`      | GET /api/v2/me            | Active |
| `rust_auth_logout`  | POST /api/v2/auth/logout  | Active |

### Level 2: Full Service (Container Stop)

Use when the Rust gateway is broadly broken.

```bash
cd /home/autoniix/autoniix
docker compose stop rust-gateway

# Verify Python dashboard is handling all traffic
docker compose ps dashboard-bff
curl -fsS http://localhost:8020/health
```

### Level 3: Database Rollback

Use when database schema is corrupted or incompatible.

```bash
# Connect to the database
docker compose exec -T postgres-app psql -U app -d autoniix

# Check for orphaned data from Rust
SELECT COUNT(*) FROM users WHERE email LIKE '%@rust.%';
SELECT COUNT(*) FROM sessions WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE '%@rust.%'
);

# If cleanup needed:
DELETE FROM sessions WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE '%@rust.%'
);
DELETE FROM workspace_members WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE '%@rust.%'
);
DELETE FROM workspaces WHERE owner_user_id IN (
  SELECT id FROM users WHERE email LIKE '%@rust.%'
);
DELETE FROM users WHERE email LIKE '%@rust.%';
```

---

## Automatic Rollback Triggers

| Trigger               | Threshold                 | Action                        |
| --------------------- | ------------------------- | ----------------------------- |
| Error rate            | > 0.1% for 5 min          | Auto-rollback to Python       |
| p95 latency           | > Python + 20% for 10 min | Auto-rollback                 |
| 5xx spike             | > 10/min                  | Auto-rollback                 |
| Equivalence test fail | In prod sampling          | Page on-call, manual decision |

---

## Verification After Rollback

```bash
# Health check
curl -fsS http://localhost:8020/health | python3 -m json.tool

# Auth smoke test
curl -fsS -X POST http://localhost:8020/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@autoniix.com","password":"test"}' | head -c 200

# Watch error rate for 30 minutes
watch -n 30 'curl -fsS http://localhost:8020/metrics | grep -E "http_requests_total|auth_failed"'
```

---

## Session Continuity Notes

Sessions created by Rust are stored in the `sessions` table with the same schema as Python. After rollback:

- **Active JWTs (access tokens):** Continue working until expiry (1 hour). Python can decode them because `AUTH_JWT_SECRET` is shared.
- **Refresh tokens:** Opaque tokens stored in `sessions`. Python can refresh them — table schema is shared.
- **No action needed** in the normal case.

---

## Post-Rollback Actions

1. **Document the incident** in the migration tracking issue
2. **Run equivalence tests** locally: `cargo test -p harness equivalence -- --nocapture`
3. **Run schema compatibility tests:** `cargo test --test schema_compatibility_test`
4. **Fix the Rust gateway** before re-enabling
5. **Get sign-off** from migration lead before re-deploying
