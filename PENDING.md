# PENDING

Source of truth for deferred work. Updated as items land or new ones surface.

Convention: every item has a **trigger** — the concrete signal that says
"now's the time." If there's no trigger yet, leave the item alone. The
discipline is *not* to do these because they're listed; the discipline is
to wait for the trigger.

> **For Cascade**: when the user runs `/check-pending` or asks
> "what's pending?", read this file and only surface items whose trigger
> has fired. Don't recommend the deferred list unless asked.

Items are grouped:
1. **Active bugs** — triggers already fired; fix on next session.
2. **Deferred (deployment / scale)** — wait for the deploy or scale event.
3. **Deferred (long-horizon)** — wait for real signal, not a calendar.

---

# 1. ACTIVE BUGS — TRIGGER FIRED

*No active bugs.* All known issues resolved through Phase F (May 11, 2026).

---

# 2. DEFERRED — DEPLOYMENT / SCALE

## first-deploy-checklist — run on server before going live

**Status:** ready — all tooling is in place
**Trigger:** next deployment to a real server

```bash
# Run in order — all commands are idempotent
git pull origin main
docker compose build
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/init-db.sql    # apply schema
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/seed-data.sql  # seed config
make up
make health
make schedule-register                           # 5 Temporal schedules
make auth-enable                                 # flip to v2 auth
make smoke
```

Remaining manual steps after stack is up:

- [ ] **OAuth scope check** — existing OAuth client must have
      `https://www.googleapis.com/auth/yt-analytics.readonly` alongside
      `youtube.upload`. RetentionFetchWorkflow throws 403 without it.
- [ ] **Phase 8 backfill** — run `refresh_niche_pulse_activity` manually
      for each active niche to seed the NichePulse tables immediately.
- [ ] **Phase 9 backfill** — invoke `RetentionFetchWorkflow` with
      `{"limit": 200}` once to pull curves for the existing 7-30 day
      window. Without it, calibrator falls back to tier labels until the
      daily cron catches up.
- [ ] **Phase 11 first retrain** — after 30+ delivered videos with
      analytics ingested, manually trigger `train_model(niche=...)` for
      one channel and verify `n_weighted_samples > 0` in the response.
- [ ] **backup-restore-drill** — run `make backup` → destroy test DB →
      `make restore` → `make smoke` and record result in runbook.
      Trigger: before production go-live (or monthly thereafter).

**Watch windows after deploy:**

| Window | What to watch |
|--------|--------------|
| Week 1 | `alert-rules-calibration` — 5% error rate, 5s p95 latency are defaults; tune against observed baselines |
| Days 7-30 | Phase 10: Diversity Floor panel — sustained 0% = good or too loose; >25% = too aggressive |
| Days 7-14 | Phase 11: Prediction Calibration panel populates; Brier < 0.20 = healthy |
| Week 2+ | Phase 11: `weighted_fraction` should rise from 0% toward 30-60% |

---

## phase-11-12-hardening — remaining pre-public items

**Status:** partially done (TLS, SSH/UFW documented, node-exporter installed)
**Trigger:** moving to multi-user / public deployment

- [ ] Circuit breaker behavior under sustained service-down conditions
      (housekeeping retries, backoff). Not yet load-tested end-to-end.
- [ ] Cross-channel dedup tested with ≥3 channels running simultaneously.
      No fixture today demonstrates dedup actually triggers.
- [ ] Sustained 10-channel concurrent load test (today only
      `tests/load/test_fleet_health_under_load.py` covers a single endpoint).

---

## legacy-api-removal — remove 42 deprecated `/api/*` endpoints

**Status:** deprecated with `deprecated=True` in OpenAPI (Phase E)
**Trigger:** `auth.v2.enabled=TRUE` in production for ≥2 weeks AND
zero errors for deprecated paths in Grafana/Loki.

Remove endpoints in two passes:
1. Read endpoints first (`GET /api/channels`, `GET /api/jobs/*`, etc.)
2. Write endpoints second (`POST /api/channels/{id}/trigger`, etc.)

Legacy `dashboard/src/lib/api.ts` can be deleted at the same time.

---

## storage-failover — MinIO + R2 tee writer

**Status:** deferred during Phase 6
**Trigger:** first MinIO outage OR first request to serve from a second region.

- [ ] Add `tee` storage provider — writes to MinIO (primary) + R2 (secondary)
      in parallel, fails only if both fail.
- [ ] Read path: try MinIO, fall back to R2 on 404 / connection error.
- [ ] Replication audit job comparing object counts weekly.

`storage_provider` is already a registered abstraction in `src/config.py` —
no existing call sites need to change.

---

## multi-tenancy — per-tenant DB schemas + secret isolation

**Status:** deferred during Phase 6
**Trigger:** a second human logs into the dashboard.

Until then there's nothing to isolate. Don't pre-build it.

---

## postgres-read-replicas

**Status:** deferred
**Trigger:** sustained `db_pool.pressure > 0.5` on `/api/fleet-health`
for >1 hour, OR query latency p99 climbing on the slow-query log.

---

## worker-auto-scaling — HPA on queue depth

**Status:** deferred
**Trigger:** Temporal queue depth visibly backs up during peak runs
(fleet panel + Temporal UI).

---

# 3. DEFERRED — LONG-HORIZON

## cross-niche-transfer-learning

**Status:** deferred
**Trigger:** ≥6 months of per-niche calibrator data accumulated AND
clear evidence small-niche channels would benefit from adjacent priors.

---

## load-test-graduation — k6 / locust for sustained-rate testing

**Status:** deferred
**Trigger:** `tests/load/test_fleet_health_under_load.py` is no longer
expressive enough (ramp-up curves, multi-region, sustained-rate needed).

---

# 4. DONE — brief changelog

| Phase | Date | Summary |
|-------|------|---------|
| **F** Production Deploy | May 11, 2026 | `scripts/register_schedules.py` (5 Temporal schedules), SSH/UFW runbook, `make smoke` / `make deploy-check` / `make schedule-register` |
| **E** Single Source of Truth | May 11, 2026 | `api-v2.ts` + session utilities, 9 UI pages migrated off `api.ts`, `api.ts` `@deprecated`, 42 legacy endpoints `deprecated=True` |
| **D** Cost & Quality Hardening | May 10, 2026 | 6 new Prometheus metrics, budget gauge refresh background task, node-exporter, 348 tests passing |
| **C** Operational Confidence | May 10, 2026 | Alertmanager (12 rules), restore script, 30d log retention, Grafana alerting, operations runbook |
| **B** Auth & Secrets | May 10, 2026 | Dual-mode login, JWT secret guards, Traefik TLS, rate limiting, SBOM/vuln CI scan |
| **A** Foundations | May 10, 2026 | Fleet health ports, v2 router fail-loud, restart-app all services, CORS allowlist, rich `/health` endpoint |
| Wave 6 | May 10, 2026 | BFF v2 jobs/system API, all UI pages migrated to v2, restart/retry/stop job lifecycle |
