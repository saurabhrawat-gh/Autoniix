# PENDING

Source of truth for deferred work. Updated as items land or new ones surface.

Convention: every item has a **trigger** — the concrete signal that says
"now's the time." If there's no trigger yet, leave the item alone. The
discipline is *not* to do these because they're listed; the discipline is
to wait for the trigger.

> **For Cascade**: when the user runs `/check-pending` or asks
> "what's pending?", read this file and only surface items whose trigger
> has fired. Don't recommend the deferred list unless asked.

---

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
