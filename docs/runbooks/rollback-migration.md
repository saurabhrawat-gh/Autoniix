# Migration Rollback Runbook

**Status:** Active  
**Last Updated:** 2026-06-20  
**Applies To:** Python → Rust/Go multi-language backend migration

---

## Overview

This runbook covers rolling back any migrated endpoint from Rust/Go back to
Python. Each endpoint has a feature flag (`rust_<service>_<endpoint>`) that
can be disabled in <60 seconds without a deploy.

---

## Rollback Levels

### Level 1: Single Endpoint (Feature Flag)

Use when one endpoint is misbehaving but the rest of the Rust gateway is fine.

```bash
# Disable specific endpoint flag
# Via Unleash/LaunchDarkly UI or API:
curl -X PUT https://unleash.local/api/features/rust_auth_signup \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'
```

### Level 2: Full Service (Container Stop)

Use when the Rust gateway is broadly broken.

```bash
docker compose stop rust-gateway
# Python dashboard automatically handles all traffic
```

### Level 3: Database Rollback

Use when database schema is corrupted or incompatible.
See `db-migration-rollback.md`.

---

## Verification After Rollback

1. **Health check:** `curl http://localhost:8020/health`
2. **Auth smoke test:**
   ```bash
   curl -X POST http://localhost:8020/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"test@autoniix.com","password":"test"}'
   ```
3. **Metrics:** `curl http://localhost:8020/metrics | grep http_requests_total`
4. **Monitor for 30 minutes** before considering re-deployment

---

## Feature Flag Inventory

| Flag | Endpoint | Status |
|------|----------|--------|
| `rust_auth_signup` | POST /api/v2/auth/signup | Active |
| `rust_auth_signin` | POST /api/v2/auth/signin | Active |
| `rust_auth_refresh` | POST /api/v2/auth/refresh | Active |
| `rust_auth_me` | GET /api/v2/me | Active |
| `rust_auth_logout` | POST /api/v2/auth/logout | Active |

**Kill-switch SLA:** Disable any flag in <60 seconds without deploy.
