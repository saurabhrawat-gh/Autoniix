# Migration Guide: Polyglot → Two-Language

**Status:** Phases 0–5 complete, ready for Phase 6  
**Timeline:** 4 weeks (Aug 1 – Aug 29, 2026)  
**Owner:** Saurabh Rawat

This document tracks the 7-phase migration from polyglot (Rust+Go+Python+TS) to two-language (Python+TS).

See: `docs/architecture/adr-004-two-language-simplification.md`

---

## Phase Overview

| Phase | Duration | Status | Deliverable |
|-------|----------|--------|-------------|
| 0. Freeze + ADR | 1 day | ✅ **DONE** | ADR-004, harness docs, this file |
| 1. Contracts | 2–3 days | ✅ **DONE** | Zod schemas + Pydantic codegen |
| 2. Gateway | 5–7 days | ✅ **DONE** | Node Fastify BFF (41 endpoints + 2 cron) |
| 3. Streaming | 2 days | ✅ **DONE** | Node WS/SSE service |
| 4. Temporal | 3–4 days | ✅ **DONE** | Python workers + workflows |
| 5. Services | 5–7 days | ✅ **DONE** | notification-dispatcher-v2 |
| 6. Delete | 1 day | ⏳ Pending | Remove Rust/Go/proto |
| 7. Standardize | 3–4 days | ⏳ Pending | Full harness applied |

---

## Phase 0: Freeze + ADR ✅

**Completed:** 2026-08-01

**Deliverables:**
- ✅ `docs/architecture/adr-004-two-language-simplification.md`
- ✅ `docs/harness/README.md`
- ✅ `MIGRATION.md` (this file)

**Actions taken:**
- Documented decision to collapse to Python + TypeScript
- Defined 7-phase migration plan
- Locked standardization harness (lint/format/test/CI)

**Next:** Phase 1 (Contracts)

---

## Phase 1: Contracts Layer 🔄

**Goal:** Replace Protocol Buffers with Zod → OpenAPI → Pydantic

**Duration:** 2–3 days

**Deliverables:**
1. `libs/ts/contracts/` package with Zod schemas
2. `libs/python/contracts/` with generated Pydantic models
3. `make gen-contracts` command
4. Contract round-trip tests

**Tasks:**

### 1.1 Create TypeScript contracts package
- [ ] Create `libs/ts/contracts/package.json`
- [ ] Install deps: `zod`, `@asteasolutions/zod-to-openapi`
- [ ] Create base schemas (channel, content, job, user, workspace)
- [ ] Export OpenAPI spec generator
- [ ] Add to pnpm workspace

### 1.2 Set up Python contracts package
- [ ] Create `libs/python/contracts/pyproject.toml`
- [ ] Install `datamodel-code-generator`
- [ ] Create codegen script: `tools/gen-pydantic.sh`
- [ ] Add to uv workspace

### 1.3 Implement codegen pipeline
- [ ] `make gen-contracts` in Makefile
- [ ] Generate OpenAPI JSON from Zod
- [ ] Generate Pydantic from OpenAPI
- [ ] Verify round-trip (TS → OpenAPI → Pydantic → JSON → TS)

### 1.4 Port critical schemas
- [ ] Channel (from `proto/autoniix/v1/channel.proto`)
- [ ] Content (from `proto/autoniix/v1/content.proto`)
- [ ] Job (from `proto/autoniix/v1/job.proto`)
- [ ] User/Auth (from `proto/autoniix/v1/auth.proto`)
- [ ] Workspace (from `proto/autoniix/v1/workspace.proto`)

### 1.5 Add contract tests
- [ ] TypeScript: validate Zod schemas parse correctly
- [ ] Python: validate Pydantic models parse correctly
- [ ] Round-trip: TS → JSON → Python → JSON → TS

**Rollback:** Delete `libs/ts/contracts` and `libs/python/contracts`. No impact.

**Success criteria:**
- ✅ `make gen-contracts` runs without errors
- ✅ All contract tests green
- ✅ OpenAPI spec validates (via `swagger-cli validate`)

---

## Phase 2: Gateway Rewrite ⏳

**Goal:** Replace Rust gateway with Node Fastify

**Duration:** 5–7 days

**Deliverables:**
1. `apps/gateway/` — Fastify app
2. Feature flag in Caddy to route traffic
3. All existing routes replicated
4. Auth middleware (JWT + cookie handling)
5. Rate limiting
6. Integration tests

**Tasks:**

### 2.1 Bootstrap Fastify app
- [ ] Create `apps/gateway/`
- [ ] Install: `fastify`, `@fastify/type-provider-zod`, `@fastify/jwt`, `@fastify/cookie`, `@fastify/rate-limit`, `@fastify/cors`
- [ ] Set up TypeScript config
- [ ] Create `src/index.ts` entrypoint
- [ ] Add to pnpm workspace + Turborepo

### 2.2 Port auth routes
- [ ] `/api/v2/auth/login` (POST)
- [ ] `/api/v2/auth/register` (POST)
- [ ] `/api/v2/auth/logout` (POST)
- [ ] `/api/v2/auth/refresh` (POST)
- [ ] `/api/v2/auth/me` (GET)
- [ ] JWT middleware
- [ ] Cookie handling (HttpOnly, Secure, SameSite)

### 2.3 Port resource routes
- [ ] `/api/v2/channels/*` (CRUD)
- [ ] `/api/v2/content/*` (CRUD)
- [ ] `/api/v2/jobs/*` (CRUD + trigger)
- [ ] `/api/v2/workspaces/*` (CRUD)
- [ ] `/api/v2/users/*` (CRUD)

### 2.4 Port utility routes
- [ ] `/api/v2/health` (GET)
- [ ] `/api/v2/openapi.json` (GET)
- [ ] `/api/v2/lookup-values/*` (GET)

### 2.5 Add middleware
- [ ] Rate limiting (per-user token bucket)
- [ ] CORS
- [ ] Request logging (structured JSON)
- [ ] Error handling (global error handler)
- [ ] OpenTelemetry tracing

### 2.6 Feature flag in Caddy
- [ ] Add env var `GATEWAY_BACKEND=rust|node`
- [ ] Update `infra/caddy/Caddyfile`:
  ```
  reverse_proxy {$GATEWAY_BACKEND}:8080
  ```
- [ ] Default to `rust` (rollback = flip env var)

### 2.7 Integration tests
- [ ] Auth flow (login → refresh → logout)
- [ ] CRUD operations (channels, content, jobs)
- [ ] Rate limiting
- [ ] Error responses (400, 401, 403, 404, 500)

**Rollback:** Set `GATEWAY_BACKEND=rust` in `.env`. Instant rollback.

**Success criteria:**
- ✅ All routes return same responses as Rust gateway
- ✅ Auth flow works (JWT + cookies)
- ✅ Integration tests green
- ✅ Load test: 1000 RPS for 1 min (no errors)

---

## Phase 3: Streaming Hub ⏳

**Goal:** Replace Rust streaming with Node WS/SSE

**Duration:** 2 days

**Deliverables:**
1. `apps/streaming-hub/` — Fastify + ws
2. SSE endpoint for progress updates
3. WebSocket endpoint for real-time events
4. Redis pub/sub integration

**Tasks:**

### 3.1 Bootstrap streaming app
- [ ] Create `apps/streaming-hub/`
- [ ] Install: `fastify`, `ws`, `ioredis`
- [ ] Set up TypeScript config
- [ ] Create `src/index.ts`

### 3.2 SSE endpoint
- [ ] `/api/v2/stream/progress/:job_id` (GET, SSE)
- [ ] Subscribe to Redis channel `job:progress:{job_id}`
- [ ] Stream events to client
- [ ] Auto-close on job completion

### 3.3 WebSocket endpoint
- [ ] `/api/v2/ws/events` (WebSocket)
- [ ] Auth via query param `?token=<jwt>`
- [ ] Subscribe to user-specific Redis channels
- [ ] Broadcast events to connected clients

### 3.4 Integration with Python services
- [ ] Python services publish to Redis
- [ ] Streaming hub consumes and forwards
- [ ] No changes to Python side

### 3.5 Feature flag in Caddy
- [ ] Route `/api/v2/stream/*` and `/api/v2/ws/*` to streaming-hub
- [ ] Default to Rust, flip to Node when ready

**Rollback:** Flip Caddy route back to Rust.

**Success criteria:**
- ✅ SSE streams job progress
- ✅ WebSocket receives real-time events
- ✅ No message loss (Redis pub/sub reliable)

---

## Phase 4: Temporal Workers ✅

**Completed:** 2026-08-02

**Deliverables:**
1. ✅ Python workflows package (`services/temporal-workers/workers/workflows/`)
2. ✅ All 8 workflows ported from Go (932 lines → 1,857 lines Python)
3. ✅ Worker entrypoints for `-v2` task queues
4. ✅ Syntax + import validation

**What Landed:**

### 4.1 Python workflows (`workers/workflows/`)
- ✅ `VideoProductionWorkflow` — 11-phase pipeline (931 lines)
  - Signals: `approve_video`, `emergency_stop`, `pause_workflow`, `resume_workflow`, `receive_brain_directive`
  - Query: `get_status`
  - Full checkpoint/resume support
  - Parallel activities (assets + thumbnail + music) via `asyncio.gather`
  - Human review await (24h timeout → auto-approve)
  - Pause/resume (24h timeout → auto-cancel)
  - Brain directive HALT/HOLD handling
- ✅ `DailySchedulerWorkflow` — fans out `VideoProductionWorkflow` per channel
- ✅ `HealthBeatWorkflow` — 5-min provider health check
- ✅ `ChangeRequestExpiryWorkflow` — hourly stale request cleanup
- ✅ `GateCalibrationWorkflow` — weekly per-niche quality gate tuning
- ✅ `NichePulseRefreshWorkflow` — weekly competitor snapshot refresh
- ✅ `RetentionFetchWorkflow` — daily audience retention batch pull
- ✅ `ModelMaintenanceWorkflow` — weekly ML model retraining + drift check
- ✅ `types.py` — shared types, retry policies, helpers

### 4.2 Worker entrypoints
- ✅ `run_production_v2.py` → `video-production-v2` queue
- ✅ `run_scheduler_v2.py` → `scheduler-v2` queue
- Activities: same set as legacy workers (no changes needed)

### 4.3 Cutover strategy
- Legacy Go workers remain on `video-production` + `scheduler` queues
- New Python workers run on `video-production-v2` + `scheduler-v2` queues
- Callers/schedules gradually switch to `-v2` queues
- When in-flight Go workflows drain, decommission Go worker

**Rollback:** Stop Python workers, all traffic remains on Go workers.

**Success criteria:**
- ✅ All 8 workflows + 2 types import cleanly
- ✅ Syntax validated (10 files)
- ✅ Retry policies match Go originals
- ✅ Parallel activity execution uses `asyncio.gather` with exception handling
- ✅ Timeout handling via `try/except TimeoutError`

---

## Phase 5: Remaining Services ✅

**Completed:** 2026-08-04

**Deliverables:**
1. ✅ `services/notification-dispatcher-v2/` — Python notification retry poller

**What Landed:**

### 5.1 notification-dispatcher-v2 (Python)
- ✅ Direct port of Go G1 service (`services/notification-dispatcher/`)
- ✅ Polls `notification_deliveries` for stuck rows (status='queued' or 'failed')
- ✅ Retries delivery via channels: slack, webhook, browser, email
- ✅ Uses `FOR UPDATE SKIP LOCKED` to avoid collisions with Go dispatcher or Python inline delivery
- ✅ Parallel delivery via `asyncio.gather` (vs Go's sequential loop)
- ✅ FastAPI health/ready endpoints
- ✅ Docker image with healthcheck
- ✅ Makefile targets: `ndisp2-build`, `ndisp2-test`, `ndisp2-dev`, `ndisp2-up`, `ndisp2-rollback`

### 5.2 Architecture
- **Channels:** Slack (webhook), Webhook (raw JSON POST), Browser (no-op), Email (placeholder)
- **Polling:** Every 15s (configurable), claims up to 50 rows per tick
- **Retry:** Max 3 attempts, then permanent failure
- **Timeout:** 10s per HTTP call

### 5.3 Cutover strategy
- Legacy Go dispatcher: `services/notification-dispatcher/` (profiles: go-services)
- New Python dispatcher: `services/notification-dispatcher-v2/` (port 8091)
- Both run side-by-side; `FOR UPDATE SKIP LOCKED` prevents double-delivery
- When confident, stop Go dispatcher and remove from docker-compose (Phase 6)

**Note:** All other services (research, script, voice, thumbnail, delivery, etc.) are already Python FastAPI under `services/api/`. No porting needed.

**Rollback:** Stop Python dispatcher, Go dispatcher handles all retries.

**Success criteria:**
- ✅ Service builds and starts
- ✅ Health/ready endpoints respond
- ✅ Polls database without errors
- ✅ Delivers notifications via configured channels

---

## Phase 6: Delete Polyglot Artifacts ⏳

**Goal:** Remove all Rust/Go/protobuf code

**Duration:** 1 day

**Deliverables:**
1. Deleted: `Cargo.*`, `go.mod`, `proto/`, `gen/go/`, `services/gateway/` (Rust), `services/harness/` (Rust)
2. Updated: `package.json`, `docker-compose.yml`, `.gitignore`, CI workflows
3. Updated: `versions.env` (remove Rust/Go/Buf)

**Tasks:**

### 6.1 Delete files
- [ ] `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`
- [ ] `go.mod`, `go.sum`, `.go-version`
- [ ] `proto/` (entire directory)
- [ ] `gen/go/` (entire directory)
- [ ] `services/gateway/` (Rust)
- [ ] `services/harness/` (Rust)
- [ ] `.golangci.yml`, `rustfmt.toml`

### 6.2 Update configs
- [ ] `package.json` — remove Rust/Go scripts, update workspaces
- [ ] `docker-compose.yml` — remove Rust/Go services
- [ ] `.gitignore` — remove Rust/Go ignores
- [ ] `versions.env` — remove Rust/Go/Buf pins
- [ ] `.mise.toml` — remove Rust/Go tools

### 6.3 Update CI
- [ ] Delete `.github/workflows/rust-*.yml`
- [ ] Delete `.github/workflows/go-*.yml`
- [ ] Delete `.github/workflows/proto-*.yml`
- [ ] Update `.github/workflows/ci.yml` (remove Rust/Go jobs)

### 6.4 Update docs
- [ ] `README.md` — update stack description
- [ ] `.devin/rules/architecture.md` — update language list

**Rollback:** `git revert` the delete commit. Rebuild Rust/Go images.

**Success criteria:**
- ✅ Zero Rust/Go/protobuf files in repo
- ✅ `make build` succeeds (only Python/TS images)
- ✅ `make up` succeeds (all services start)
- ✅ CI green

---

## Phase 7: Standardization ⏳

**Goal:** Apply full harness (lint/format/test/CI)

**Duration:** 3–4 days

**Deliverables:**
1. All Python code passes Ruff (format + lint)
2. All TypeScript code passes Prettier + ESLint
3. All code passes type checks (mypy, basedpyright, tsc)
4. 80%+ test coverage
5. CI runs in <6 min
6. Pre-commit hooks installed

**Tasks:**

### 7.1 Python standardization
- [ ] Create `ruff.toml` (root)
- [ ] Run `ruff format .` (auto-fix all)
- [ ] Run `ruff check --fix .` (auto-fix lints)
- [ ] Fix remaining lint errors manually
- [ ] Add type hints to all public APIs
- [ ] Run `mypy libs/python/` (fix errors)
- [ ] Run `basedpyright services/` (fix errors)

### 7.2 TypeScript standardization
- [ ] Create `.prettierrc.json` (root)
- [ ] Create `eslint.config.mjs` (root)
- [ ] Run `prettier --write .` (auto-fix all)
- [ ] Run `eslint --fix .` (auto-fix lints)
- [ ] Fix remaining lint errors manually
- [ ] Run `tsc --noEmit` (fix type errors)

### 7.3 Testing
- [ ] Add missing unit tests (target 80% coverage)
- [ ] Add integration tests (DB, Redis)
- [ ] Add contract tests (schema round-trip)
- [ ] Add E2E tests (Playwright, critical flows)
- [ ] Run `pytest --cov` (verify 80%+)
- [ ] Run `vitest --coverage` (verify 80%+)

### 7.4 CI updates
- [ ] Rewrite `.github/workflows/ci.yml` (new structure)
- [ ] Add coverage upload (Codecov)
- [ ] Add security audit (`pip-audit`, `npm audit`)
- [ ] Add bundle size check (`@next/bundle-analyzer`)
- [ ] Verify CI runs in <6 min

### 7.5 Pre-commit hooks
- [ ] Install `lefthook`
- [ ] Create `lefthook.yml`
- [ ] Run `lefthook install`
- [ ] Test: make a change, commit (hooks should run)

### 7.6 Documentation
- [ ] Update `README.md` (new stack, new commands)
- [ ] Create `docs/harness/python-conventions.md`
- [ ] Create `docs/harness/typescript-conventions.md`
- [ ] Update all workflow docs in `.devin/workflows/`

**Rollback:** N/A (standardization is additive, not destructive)

**Success criteria:**
- ✅ Zero lint errors
- ✅ Zero format diffs
- ✅ Zero type errors
- ✅ 80%+ test coverage
- ✅ CI green in <6 min
- ✅ Pre-commit hooks working

---

## Rollback Strategy

Each phase has an independent rollback:

| Phase | Rollback Action | Time |
|-------|----------------|------|
| 1 | Delete `libs/ts/contracts` and `libs/python/contracts` | 1 min |
| 2 | Set `GATEWAY_BACKEND=rust` in `.env` | 1 min |
| 3 | Flip Caddy route back to Rust streaming | 1 min |
| 4 | Restart Go worker, stop Python worker | 1 min |
| 5 | Restart Go services, stop Python services | 1 min |
| 6 | `git revert` delete commit, rebuild images | 10 min |
| 7 | N/A (additive only) | — |

**Critical:** Never delete Rust/Go code until Phase 6. Keep it idle but runnable.

---

## Success Metrics

**After Phase 7, we should have:**

1. ✅ Zero Rust/Go/protobuf code
2. ✅ CI runs in <6 min (vs current 20+ min)
3. ✅ Docker builds in <2 min (vs current 15 min)
4. ✅ All tests green
5. ✅ 80%+ code coverage
6. ✅ Zero lint/format/type errors
7. ✅ All existing features work (no regressions)
8. ✅ `make ci` passes locally in <10 min

---

## Daily Checklist

**Every day during migration:**

- [ ] Run `make ci-fast` before pushing
- [ ] Update this file with progress
- [ ] Commit to `develop` (never `main`)
- [ ] Tag commits with phase number: `[Phase N]`
- [ ] If blocked, document blocker in this file

---

## Current Blockers

None.

---

## Notes

- **Build freeze:** No Rust/Go work during migration (per ADR-004)
- **Branch strategy:** All work on `develop`, merge to `main` after Phase 7
- **Communication:** Update `#engineering` Slack daily with progress
- **Testing:** Run full test suite after each phase

---

**Last updated:** 2026-08-01 (Phase 0 complete)  
**Next update:** After Phase 1 completion
