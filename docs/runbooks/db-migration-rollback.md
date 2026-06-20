# Database Migration Rollback Runbook

**Status:** Active  
**Last Updated:** 2026-06-20  
**Applies To:** Rust gateway ↔ Python dashboard migration

---

## When to Use This Runbook

- Rust gateway is producing errors after a deployment
- Database schema incompatibility detected
- JWT token validation failures across services
- Equivalence tests failing in production sampling

---

## Rollback Procedure

### Step 1: Disable Rust Gateway (Immediate)

```bash
# On the VPS
cd /home/autoniix/autoniix

# Disable the Rust gateway feature flag (if using Unleash/LaunchDarkly)
# Or stop the Rust container directly:
docker compose stop rust-gateway

# Verify Python dashboard is handling all traffic
docker compose ps dashboard-bff
curl -fsS http://localhost:8020/health
```

### Step 2: Verify Python Dashboard Is Healthy

```bash
# Check health
curl -fsS http://localhost:8020/health | python3 -m json.tool

# Check DB connectivity
curl -fsS http://localhost:8020/health | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('DB:', d.get('components',{}).get('db'))"

# Check auth endpoint
curl -fsS -X POST http://localhost:8020/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@autoniix.com","password":"test"}' | head -c 200
```

### Step 3: Handle In-Flight Sessions

Sessions created by Rust are stored in the `sessions` table with the same
schema as Python. After rollback:

- **Active JWTs (access tokens):** Will continue to work until expiry (1 hour).
  Python can decode them because `AUTH_JWT_SECRET` is shared.
- **Refresh tokens:** Opaque tokens stored in `sessions`. Python can refresh
  them because the table schema is shared.
- **No action needed:** Both services read/write the same `sessions` table.

### Step 4: Verify Database State

```bash
# Connect to the database
docker compose exec -T postgres-app psql -U app -d autoniix

# Check for any orphaned data from Rust
SELECT COUNT(*) FROM users WHERE email LIKE '%@rust.%';
SELECT COUNT(*) FROM workspaces WHERE slug LIKE 'rust-%';
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

### Step 5: Monitor Post-Rollback

```bash
# Watch error rate for 30 minutes
watch -n 30 'curl -fsS http://localhost:8020/metrics | grep -E "http_requests_total|auth_failed"'

# Check Grafana for error spikes
# Dashboard: http://grafana.local/d/autoniix-overview
```

---

## Rollback Triggers (Automatic)

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Error rate | > 0.1% for 5 min | Auto-rollback to Python |
| p95 latency | > Python + 20% for 10 min | Auto-rollback |
| 5xx spike | > 10/min | Auto-rollback |
| Equivalence test fail | In prod sampling | Page on-call, manual decision |

---

## Emergency Contacts

- **Migration Lead:** See team Slack channel `#migration`
- **SRE On-Call:** PagerDuty rotation
- **Database Admin:** See wiki `Operations-Runbook.md`

---

## Post-Rollback Actions

1. **Document the incident** in the migration tracking issue
2. **Run equivalence tests** locally to identify the divergence
3. **Fix the Rust gateway** before re-enabling
4. **Re-run schema compatibility tests** (`cargo test --test schema_compatibility_test`)
5. **Get sign-off** from migration lead before re-deploying
