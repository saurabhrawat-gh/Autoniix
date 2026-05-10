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
2. **Deferred (Wave 6 follow-ups)** — partial migration items.
3. **Deferred (deployment / scale)** — wait for the deploy or scale event.
4. **Deferred (long-horizon)** — wait for real signal, not a calendar.

---

# 1. ACTIVE BUGS — TRIGGER FIRED

## fleet-health-port-map — wrong ports for every service

**Status:** active bug, surfaced May 10, 2026
**Trigger:** anyone opens `/dashboard/fleet` and sees most services red

`src/services/dashboard/main.py:_FLEET_SERVICES` maps each service to a
URL whose port is **not** what `docker-compose.yml` actually binds. Every
entry except `admin` (just fixed) is wrong:

| Service     | Map says | Compose says |
|-------------|----------|--------------|
| research    | 8011     | 8001         |
| script      | 8012     | 8002         |
| voice       | 8013     | 8003         |
| assets      | 8014     | 8004         |
| thumbnail   | 8015     | 8005         |
| direction   | 8016     | 8010         |
| music       | 8017     | DOES NOT EXIST |
| assembly    | 8018     | 8006         |
| delivery    | 8019     | 8007         |
| analytics   | 8020     | 8008  *(also conflicts with dashboard-bff:8020)* |
| brand       | 8021     | 8012         |
| editor      | 8022     | 8013         |
| admin       | 8009 ✓   | 8009         |

Fix is a one-shot sync. Better long-term: derive from `observability/prometheus.yml`
(which has the right ports) or the compose file, so this can't drift again.

---

## music-service-phantom — fleet probe targets a service that doesn't exist

**Status:** active bug, surfaced May 10, 2026
**Trigger:** same as `fleet-health-port-map` — fix together.

`_FLEET_SERVICES` includes `"music": "http://music:8017/health"` but
there's no `src/services/music/` and no `music` entry in
`docker-compose.yml`. Music functionality lives inside `assets`. Drop
the entry. If a dedicated music service is added later, re-introduce.

---

## v2-router-fail-loud — silent try/except hides BFF boot errors

**Status:** mitigated by `make verify-bff`, root cause untouched
**Trigger:** the next time a BFF boot failure goes unnoticed in CI/dev
(i.e., someone deploys without running `make verify-bff` afterward).

`src/services/dashboard/main.py:124-128`:

```python
try:
    from src.services.dashboard.v2 import router as _v2_router
    app.include_router(_v2_router, prefix="/api/v2")
except Exception as _exc:  # pragma: no cover — never fail boot on v2
    logger.warning("dashboard.v2_router_disabled", error=str(_exc))
```

Hides syntax errors, missing deps, and import failures behind a `warning`
log. Today this trap cost ~30 minutes of debugging (missing
`python-multipart` + `experiments.py` syntax error were both caught only
after we built `make verify-bff`). Better long-term:

- Surface `v2_router_loaded: false` on `GET /health`, OR
- Re-raise when `ENVIRONMENT_MODE != "production"`.

---

## restart-app-incomplete — workers/services skipped on shared `src/` edits

**Status:** dev-loop friction, surfaced May 10, 2026
**Trigger:** edit a file under `src/providers/`, `src/intelligence/`,
`src/llm/`, or `src/temporal_workflows/` and observe the change is *not*
visible in the 12 application services until a full rebuild.

`make restart-app` rebuilds:
`dashboard-bff dashboard-ui admin worker-production worker-scheduler`

It does **not** rebuild the 12 application services (research, script,
voice, assets, thumbnail, direction, assembly, delivery, analytics,
brand, editor, sheets-sync) even though they share the same Docker
image base (`build: .`). Edits in shared `src/` modules don't take
effect in those services without `docker compose build` over the full
set.

Options when triggered:
- (a) Expand `restart-app` to include all 12 services (slow on cold
      cache, fast with layer cache).
- (b) Add a separate `make rebuild-services` target.
- (c) Add a `make rebuild` target that does everything plus restarts.

---

# 2. DEFERRED — WAVE 6 FOLLOW-UPS

## v2-auth-login-ui — migrate `/login` to v2 (email + MFA + register link)

**Status:** deferred during Wave 6
**Trigger:** `auth.v2.enabled` flag flips to TRUE, OR a second human
collaborator joins, OR someone needs MFA for compliance.

Current state: `dashboard/src/app/login/page.tsx` still uses the legacy
single-password `api.login(password)` flow. The v2 backend already has
full auth (`/api/v2/auth/login`, `/register`, `/forgot`, `/reset`,
`/mfa/setup`, `/mfa/verify`) and a `/register` page exists at
`app/register/page.tsx`, but `/login` is unmigrated and `/register` is
not linked from anywhere.

Outstanding UI work when triggered:
- Add email field + password field + MFA challenge step to `/login`.
- Wire forgot-password and registration links from `/login`.
- Detect which auth backend is active via `flagsApi.list()` and render
  the matching form (single-password vs. email+MFA).
- After login, store v2 tokens via `setV2Tokens(...)` instead of legacy
  `setToken(...)`.

Once flipped, v2 auth replaces the shared password and MFA can be
enforced per role.

---

## v2-router-strictness — drop legacy `/api/*` after full migration

**Status:** deferred during Wave 6
**Trigger:** all UI pages free of `from '@/lib/api'` *except* the four
intentional utility imports (`isLoggedIn`, `setToken`, `wsEvents`,
`wsProgress`), AND `auth.v2.enabled = TRUE` for at least 2 weeks.

Today the legacy `src/services/dashboard/main.py` is ~2000 lines
exposing every `/api/*` endpoint. v2 mirrors most of them under
`/api/v2/*`. Once Wave 6 is fully bedded in:

- Move `wsEvents` + `wsProgress` + `isLoggedIn` + `setToken` to
  `api-v2.ts` so `dashboard/src/lib/api.ts` can be deleted.
- Mark each legacy `/api/*` endpoint that has a v2 equivalent as
  `deprecated=True` in OpenAPI for one release.
- Then snapshot-test the legacy contract one final time and remove the
  endpoints in two passes (read endpoints first, then write).

Don't start until the trigger fires — there's still value in keeping the
fallback while the v2 surface is being shaken out.

---

# 3. DEFERRED — DEPLOYMENT / SCALE

## P7+P8+P9+P10+P11-deploy — apply schema + schedules

**Status:** ready to deploy
**Trigger:** next deployment

- [ ] Apply `scripts/init-db.sql` against existing Postgres (creates
      `gate_thresholds` + `retention_curves` + `bandit_picks` +
      `prediction_log`). File is idempotent (`IF NOT EXISTS`).
- [ ] Register the weekly `GateCalibrationWorkflow` schedule (Sun 04:00
      UTC). Snippet in the Phase 7 summary; one-shot script.
- [ ] Register the weekly `NichePulseRefreshWorkflow` schedule (Sun 05:00
      UTC — 1h after gate calibration so they don't fight for activity
      slots).
- [ ] Register the **daily** `RetentionFetchWorkflow` schedule
      (03:00 UTC). Daily, not weekly, so the curve-stable window
      (videos aged 7-30 days) is processed every day.
- [ ] Restart `production` + `scheduler` Temporal workers so the new
      sizing knobs take effect AND the new Phase 8/9 activities get
      registered.
- [ ] **OAuth scope check (Phase 9):** the existing OAuth client must
      have `https://www.googleapis.com/auth/yt-analytics.readonly`. If
      it only has `youtube.upload`, the retention fetcher will throw
      403 — re-auth with both scopes.
- [ ] **First-time Phase 8 backfill (optional, recommended):** run
      `refresh_niche_pulse_activity` manually for each active niche.
- [ ] **First-time Phase 9 backfill (optional):** invoke
      `RetentionFetchWorkflow` manually with `{"limit": 200}` to pull
      curves for the existing 7-30 day window all at once. Without
      this, the calibrator falls back to tier labels until the daily
      cron has caught up.
- [ ] **Phase 10 watch window:** after deploy, watch the Diversity
      Floor panel on `/fleet`. Force-rate of 0% for >2 weeks across
      multiple channels either means bandits are naturally diverse
      (good) or the threshold is too loose; >25% sustained means it's
      too aggressive and should be tuned down in
      `src/intelligence/diversity_floor.py:DIVERSITY_THRESHOLD`.
      No urgency either way — the floor is a safety net, not a
      primary control.
- [ ] **Phase 11 watch window:** the Prediction Calibration panel
      starts populating once trained models exist *and* analytics
      back-fills `prediction_log.actual_outcome`. First scored
      predictions arrive 7-14 days after first delivery. Watch:
      Brier > 0.30 = model is actively counter-signal (investigate
      data drift / feature pipeline); Brier in 0.20-0.30 = noisy
      but useful; Brier < 0.20 = healthy. ECE > 0.20 means model is
      overconfident. The `weighted_fraction` should rise from 0%
      toward 30-60% over the first month as the loop accumulates
      scored predictions; if it stays at 0%, the join from
      `research_features` to `prediction_log` is broken (most likely
      the workflow isn't forwarding `content_id` — verify the Phase
      11 plumbing in `video_production.py:304-315`).
- [ ] **Phase 11 first retrain:** after deploy, manually trigger
      `train_model(niche=...)` for one channel after at least 30
      delivered videos with analytics ingested. Verify the returned
      metrics include non-zero `n_weighted_samples` — that's the
      signal that the calibration loop has actually fed back into
      training. Without this verification, Phase 11 could be silently
      no-op'd by a missing schema migration or workflow plumbing
      regression.

---

## phase-11-12-hardening — TLS, SSH, firewall, dedup, scale tests

**Status:** deferred per `docs/10-BUILD-ORDER.md` Phase 11-12
**Trigger:** moving from single-developer dev box to multi-user / public
deployment, OR the first non-dev domain pointing at the stack.

Items:
- [ ] TLS via Traefik + Let's Encrypt (config exists, certs not provisioned).
- [ ] SSH hardening (key-only, non-standard port, fail2ban).
- [ ] UFW firewall rules limiting inbound to 80/443/SSH.
- [ ] Circuit breaker behavior verified at scale (housekeeping retries,
      backoff under sustained service-down conditions).
- [ ] Cross-channel dedup tested with ≥3 channels running simultaneously
      (today no fixture demonstrates dedup actually triggers).
- [ ] Sustained 10-channel concurrent load test (today only
      `tests/load/test_fleet_health_under_load.py` covers a single
      endpoint).

These are all "before public deploy" tasks. Don't pre-build them.

---

## storage-failover — MinIO + R2 tee writer

**Status:** deferred during Phase 6
**Trigger:** first MinIO outage **OR** first request to serve from a
second region.

- [ ] Add `tee` storage provider that writes to MinIO (primary) and
      R2 (secondary) in parallel, fails the request only if both fail.
- [ ] Read path: try MinIO, fall back to R2 on 404 / connection error.
- [ ] Replication audit job that compares object counts weekly.

`storage_provider` is already a registered abstraction in `src/config.py`,
so this is a pure addition — no existing call sites need to change.
Backup script (`scripts/backup.sh`) already handles R2 push for cold
backups; this is the hot-path tee.

---

## multi-tenancy — per-tenant DB schemas + secret isolation

**Status:** deferred during Phase 6
**Trigger:** a second human logs into the dashboard.

Until then there's nothing to isolate. Don't pre-build it.

---

## postgres-read-replicas

**Status:** deferred during Phase 6
**Trigger:** sustained `db_pool.pressure > 0.5` on `/api/fleet-health`
for >1 hour, OR query latency p99 climbing on the slow-query log.

Current bottleneck is LLM cost, not DB read load. Revisit when the
fleet panel actually shows pressure.

---

## worker-auto-scaling — HPA on queue depth

**Status:** deferred during Phase 6
**Trigger:** Temporal queue depth visibly backs up during peak runs
(visible in fleet panel + Temporal UI).

Temporal already exposes the metrics; HPA wiring is platform-specific
(k8s vs docker-swarm), so this is a deploy-time concern, not a code
concern.

---

# 4. DEFERRED — LONG-HORIZON

## test-suite-hygiene — fix or quarantine the 12 pre-existing failures

**Status:** known broken before Phase 3
**Trigger:** any time CI flakiness becomes annoying, or before opening
the codebase to a second contributor

- [ ] `tests/test_observability.py` (5 tests) — needs live Postgres
- [ ] `tests/test_ab_framework.py` (4 tests) — needs live Postgres
- [ ] `tests/test_analytics_intelligence.py::test_insufficient_data`
- [ ] `tests/test_assembly_intelligence.py::test_high_complexity_longer`
- [ ] `tests/test_delivery_intelligence.py::test_max_tags`

Quickest fix: tag with `@pytest.mark.integration` and run them only
when `INTEGRATION=1` is set. Best fix: a `pytest-postgresql` fixture
that spins up a clean DB per test.

---

## cross-niche-transfer-learning

**Status:** deferred during Phase 7
**Trigger:** ≥6 months of per-niche calibrator data accumulated, AND
clear evidence that small-niche channels would benefit from adjacent
priors (e.g. `health_recovery` cold-starts but `health_sleep` is mature).

Premature without the data — there's nothing to transfer *from* yet.

---

## load-test-graduation — k6 / locust for sustained-rate testing

**Status:** deferred during Phase 6
**Trigger:** `tests/load/test_fleet_health_under_load.py` is no longer
expressive enough — typically when ramp-up curves, multi-region tests,
or sustained-rate (not burst) load become needed.

Pure-pytest harness covers the current need. Don't graduate early.

---

# 5. DONE — kept for traceability

These were on the deferred list and are now resolved. Keeping a brief
note here so future sessions don't re-open the file thinking the trigger
might be live.

- **wave6-bff-jobs-system** — `src/services/dashboard/v2/jobs.py` and
  `system.py` shipped May 10, 2026 with all UI pages migrated.
- **dashboard-bff-stale-image** — `make restart-bff` + `make verify-bff`
  added so the silent stale-container trap can't recur.
- **admin-port-mismatch** — `experiments.py` and the fleet probe map
  now point at `admin:8009` (was `admin:8023`). Admin `/metrics` works
  after rebuild.
- **python-multipart-missing** — added to `requirements.txt`; was
  silently disabling the entire v2 router because `library.py` imports
  `Form()`/`File()`.

