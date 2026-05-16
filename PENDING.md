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

See `docs/DEPLOYMENT-GUIDE.md` for the full step-by-step. Quick recap:

```bash
# Run in order — all commands are idempotent
bash scripts/vps_bootstrap.sh           # one-shot VPS hardening
cp .env.production.example .env && $EDITOR .env
make deploy-check
docker compose --profile tls up -d --build
make schedule-register                  # 5 Temporal schedules
make auth-enable                        # flip to v2 auth
make smoke
```

Remaining manual steps after stack is up:

- [ ] **OAuth scope check** — existing OAuth client must have
      `https://www.googleapis.com/auth/yt-analytics.readonly` alongside
      `youtube.upload`. RetentionFetchWorkflow throws 403 without it.
- [ ] **Phase 8 backfill** — run `refresh_niche_pulse_activity` manually
      for each active niche to seed the NichePulse tables immediately.
- [ ] **Phase 9 backfill** — invoke `RetentionFetchWorkflow` with
      `{"limit": 200}` once to pull curves for the existing 7-30 day window.
- [ ] **Phase 11 first retrain** — after 30+ delivered videos with analytics
      ingested, manually trigger `train_model(niche=...)` for one channel.
- [ ] **backup-restore-drill** — run `make backup` → destroy test DB →
      `make restore` → `make smoke` and record result in runbook.

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
**Trigger:** Temporal queue depth visibly backs up during peak runs.

---

# 3. DEFERRED — LONG-HORIZON

## cross-niche-transfer-learning

**Status:** deferred
**Trigger:** ≥6 months of per-niche calibrator data accumulated.

---

## load-test-graduation — k6 / locust for sustained-rate testing

**Status:** deferred
**Trigger:** `tests/load/test_fleet_health_under_load.py` is no longer
expressive enough.

---

# 4. DONE — brief changelog

| Phase | Date | Summary |
|-------|------|---------|
| **G** VPS Provisioning + Split-host Traefik | May 16, 2026 | `scripts/vps_bootstrap.sh` (UFW + fail2ban + Docker + swap + `/mnt/backups`), multi-host Traefik labels for `dash`/`api`/`grafana`/`prometheus`/`alerts`/`temporal` subdomains, `admin-auth` middleware via traefik service labels, `.env.production.example`, `scripts/backup.sh` rewritten for `/mnt/backups` + S3-agnostic offsite, CI deploy job extended with post-deploy `make smoke` + Slack success/failure notification, DNS automated for autoniix.com via Hostinger MCP |
| **F** Production Deploy | May 11, 2026 | `scripts/register_schedules.py` (5 Temporal schedules), SSH/UFW runbook, `make smoke` / `make deploy-check` / `make schedule-register` |
| **E** Single Source of Truth | May 11, 2026 | `api-v2.ts` + session utilities, 9 UI pages migrated off `api.ts`, `api.ts` `@deprecated`, 42 legacy endpoints `deprecated=True` |
| **D** Cost & Quality Hardening | May 10, 2026 | 6 new Prometheus metrics, budget gauge refresh background task, node-exporter, 348 tests passing |
| **C** Operational Confidence | May 10, 2026 | Alertmanager (12 rules), restore script, 30d log retention, Grafana alerting, operations runbook |
| **B** Auth & Secrets | May 10, 2026 | Dual-mode login, JWT secret guards, Traefik TLS, rate limiting, SBOM/vuln CI scan |
| **A** Foundations | May 10, 2026 | Fleet health ports, v2 router fail-loud, restart-app all services, CORS allowlist, rich `/health` endpoint |
| Wave 6 | May 10, 2026 | BFF v2 jobs/system API, all UI pages migrated to v2, restart/retry/stop job lifecycle |
