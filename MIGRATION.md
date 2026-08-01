# Migration Guide: Polyglot → Two-Language

**Status:** Phase 0 complete, ready for Phase 1  
**Timeline:** 4 weeks (Aug 1 – Aug 29, 2026)  
**Owner:** Saurabh Rawat

This document tracks the 7-phase migration from polyglot (Rust+Go+Python+TS) to two-language (Python+TS).

See: `docs/architecture/adr-004-two-language-simplification.md`

---

## Phase Overview

| Phase | Duration | Status | Deliverable |
|-------|----------|--------|-------------|
| 0. Freeze + ADR | 1 day | ✅ **DONE** | ADR-004, harness docs, this file |
| 1. Contracts | 2–3 days | 🔄 **NEXT** | Zod schemas + Pydantic codegen |
| 2. Gateway | 5–7 days | ⏳ Pending | Node Fastify BFF |
| 3. Streaming | 2 days | ⏳ Pending | Node WS/SSE service |
| 4. Temporal | 3–4 days | ⏳ Pending | Python workers |
| 5. Services | 5–7 days | ⏳ Pending | Python FastAPI services |
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

## Phase 4: Temporal Workers ⏳

**Goal:** Port Go Temporal workers back to Python

**Duration:** 3–4 days

**Deliverables:**
1. `services/workers/` — Python Temporal workers
2. All workflows ported (production, scheduler)
3. All activities ported
4. Integration tests

**Tasks:**

### 4.1 Set up Python Temporal worker
- [ ] Create `services/workers/pyproject.toml`
- [ ] Install `temporalio` Python SDK
- [ ] Create `main.py` entrypoint
- [ ] Register workflows + activities

### 4.2 Port workflows
- [ ] `VideoProductionWorkflow` (from Go)
- [ ] `DailySchedulerWorkflow` (from Go)
- [ ] Other workflows (research, script, voice, etc.)

### 4.3 Port activities
- [ ] Research activity
- [ ] Script activity
- [ ] Voice activity
- [ ] Thumbnail activity
- [ ] Assembly activity
- [ ] Direction activity
- [ ] Delivery activity

### 4.4 Update docker-compose
- [ ] Replace Go worker container with Python worker
- [ ] Update env vars
- [ ] Test locally

### 4.5 Integration tests
- [ ] Trigger workflow via API
- [ ] Verify activities execute
- [ ] Verify workflow completes
- [ ] Verify results stored in DB

**Rollback:** Restart Go worker container. Stop Python worker.

**Success criteria:**
- ✅ All workflows execute successfully
- ✅ No workflow failures in Temporal UI
- ✅ Integration tests green

---

## Phase 5: Remaining Services ⏳

**Goal:** Port Go services to Python FastAPI

**Duration:** 5–7 days

**Deliverables:**
1. `services/research/` — Python FastAPI
2. `services/script/` — Python FastAPI
3. `services/voice/` — Python FastAPI
4. `services/thumbnail/` — Python FastAPI
5. `services/delivery/` — Python FastAPI

**Tasks:**

### 5.1 Research service
- [ ] Create `services/research/`
- [ ] Port logic from Go (or existing Python if it exists)
- [ ] Expose FastAPI endpoints
- [ ] Integration tests

### 5.2 Script service
- [ ] Create `services/script/`
- [ ] Port logic
- [ ] Expose FastAPI endpoints
- [ ] Integration tests

### 5.3 Voice service
- [ ] Create `services/voice/`
- [ ] Port logic
- [ ] Expose FastAPI endpoints
- [ ] Integration tests

### 5.4 Thumbnail service
- [ ] Create `services/thumbnail/`
- [ ] Port logic
- [ ] Expose FastAPI endpoints
- [ ] Integration tests

### 5.5 Delivery service
- [ ] Create `services/delivery/`
- [ ] Port logic
- [ ] Expose FastAPI endpoints
- [ ] Integration tests

### 5.6 Update docker-compose
- [ ] Replace Go service containers with Python
- [ ] Update service discovery env vars
- [ ] Test locally

**Rollback:** Restart Go service containers. Stop Python services.

**Success criteria:**
- ✅ All services respond to health checks
- ✅ Integration tests green
- ✅ E2E workflow (trigger job → all services execute → job completes)

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
