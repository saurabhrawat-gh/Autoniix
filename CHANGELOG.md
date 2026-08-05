# Autoniix Migration Changelog

## Phase 7: Standardization & Cleanup (Aug 4, 2026) ✅

**Completed:** August 4, 2026  
**Duration:** 1 day (planned 3–4 days)

### Summary
Applied full standardization harness across the two-language codebase (Python + TypeScript). Purged all Rust/Go/protobuf artifacts. Updated all tooling, CI, and documentation to reflect the final stack.

### Changes
- ✅ Deleted all Rust code, Cargo configs, and rust-toolchain.toml
- ✅ Deleted all Go code and go.mod files
- ✅ Deleted proto/ directory and all .proto files
- ✅ Deleted gen/ (generated protobuf bindings)
- ✅ Updated ruff.toml with comprehensive linting rules
- ✅ Updated tsconfig.base.json for monorepo TypeScript
- ✅ Updated pre-commit hooks (removed Rust/Go checks, added ruff + tsc)
- ✅ Updated CI workflows to remove Rust/Go steps
- ✅ Updated Makefiles to remove Rust/Go targets
- ✅ Formatted entire Python codebase with ruff (330 files)
- ✅ Verified all TypeScript packages typecheck cleanly

### Stack
- **Backend:** Python 3.12 (FastAPI, Temporal, Pydantic)
- **Frontend:** TypeScript/Node 22 (Next.js, Fastify, Zod)
- **Contracts:** Zod → OpenAPI → Pydantic
- **Database:** PostgreSQL 15 + pgvector
- **Infra:** Docker, Traefik, Temporal, Redis

---

## Phase 6: Delete Legacy Stack (Aug 4, 2026) ✅

**Completed:** August 4, 2026  
**Duration:** 1 day

### Summary
Removed all Rust and Go code from the repository after successful migration to Python/TypeScript.

### Deleted
- `services/gateway/` (Rust Axum) — replaced by `services/gateway-v2/` (Node Fastify)
- `services/streaming-hub/` (Go) — replaced by `services/streaming-hub-v2/` (Node Fastify)
- `services/harness/` (Rust test harness)
- `proto/` (Protocol Buffer definitions)
- `rust-toolchain.toml`, `Cargo.toml`, `Cargo.lock`
- `go.mod`, `go.sum`, `.go-version`
- All `*.rs`, `*.go`, `*.proto` files

### Retained
- Python services (all in `services/api/` and `services/temporal-workers/`)
- TypeScript services (`gateway-v2`, `streaming-hub-v2`, `remotion`, `dashboard`, `marketing`)
- Contracts layer (`libs/ts/contracts/`, `libs/python/contracts/`)

---

## Phase 5: Services Migration (Aug 3–4, 2026) ✅

**Completed:** August 4, 2026  
**Duration:** 1 day (planned 5–7 days)

### Summary
Migrated remaining Go services to Python.

### Migrated Services
- `notification-dispatcher` (Go) → `notification-dispatcher-v2` (Python)
  - Slack, email, webhook channels
  - Template rendering
  - Retry logic with exponential backoff

### Details
See `services/notification-dispatcher-v2/PHASE5_MIGRATION.md` (now archived in this changelog).

---

## Phase 4: Temporal Workers (Aug 2–3, 2026) ✅

**Completed:** August 3, 2026  
**Duration:** 1 day (planned 3–4 days)

### Summary
Ported all Go Temporal workflows to Python. Registered on new task queues (`video-production-v2`, `scheduler-v2`).

### Migrated Workflows (8 total, 1,331 lines)
1. **VideoProductionWorkflow** (931 lines) — 11-phase content pipeline
   - Signals: approve_video, emergency_stop, pause/resume, receive_brain_directive
   - Queries: get_status
   - Checkpointing for resume-from-phase
2. **DailySchedulerWorkflow** (90 lines) — fans out child workflows per channel
3. **HealthBeatWorkflow** (20 lines) — 5-min provider health check
4. **ChangeRequestExpiryWorkflow** (20 lines) — hourly stale request cleanup
5. **GateCalibrationWorkflow** (40 lines) — weekly per-niche quality gate tuning
6. **NichePulseRefreshWorkflow** (40 lines) — weekly competitor snapshot
7. **RetentionFetchWorkflow** (70 lines) — daily audience retention batch pull
8. **ModelMaintenanceWorkflow** (120 lines) — weekly ML model retraining + drift check

### Worker Entrypoints
- `run_production_v2.py` — registers VideoProductionWorkflow + all activities on `video-production-v2`
- `run_scheduler_v2.py` — registers 7 periodic workflows + activities on `scheduler-v2`

### Cutover Strategy
- Both Go and Python workers run side-by-side on different task queues
- Temporal schedules gradually switched to `-v2` queues
- Go workers drained and decommissioned after all in-flight workflows completed

### Details
See `services/temporal-workers/PHASE4_MIGRATION.md` (now archived in this changelog).

---

## Phase 3: Streaming Hub (Aug 2, 2026) ✅

**Completed:** August 2, 2026  
**Duration:** 1 day (planned 2 days)

### Summary
Replaced Go streaming-hub with Node.js Fastify service supporting SSE and WebSocket.

### Implementation
- **Framework:** Fastify 5 + `@fastify/websocket` + ioredis
- **Endpoints:**
  - `GET /api/v2/stream/events` — Server-Sent Events (long-lived HTTP)
  - `GET /api/v2/ws/events` — WebSocket (bidirectional)
  - `POST /api/v2/stream/publish` — Internal publisher
  - `GET /health`, `GET /ready` — Health probes
- **Architecture:** Multi-instance safe via Redis pub/sub on `autoniix:events` channel
- **Wire format:** JSON, compatible with legacy Go hub for gradual rollout

### Rollout
- Header-gated router: `X-Gateway-Version: v2` → streaming-hub-v2
- Default traffic → legacy Go hub (until cutover)
- Instant rollback: remove header gate

---

## Phase 2: Gateway Rewrite (Jul 30 – Aug 1, 2026) ✅

**Completed:** August 1, 2026  
**Duration:** 3 days (planned 5–7 days)

### Summary
Replaced Rust Axum gateway with Node.js Fastify service. Implemented 41 REST endpoints + 2 cron jobs.

### Implementation
- **Framework:** Fastify 5 + Zod validation + JWT + Postgres
- **Endpoints:** 41 REST routes across 9 modules
  - Auth: login, register, refresh, logout, forgot-password, reset-password, me
  - Channels: CRUD + stats
  - Jobs: CRUD + cancel + retry
  - Content: CRUD + publish
  - Workspace: settings, members, invites, deletion (soft-delete with grace period)
  - User: profile, password change, account deletion
  - Notifications: list, mark-read, mark-all-read, delete
- **Cron Jobs:**
  - Workspace deletion (daily 02:00 UTC) — purges workspaces after 30-day grace period
  - (Future: retention fetch, model maintenance)
- **Middleware:** JWT auth, rate limiting, CORS, Helmet, cookie handling
- **Database:** Postgres.js with tagged template literals

### Rollout
- Deployed alongside Rust gateway on port 8021
- Traefik router with `X-Gateway-Version: v2` header gate
- Gradual traffic shift via header
- Instant rollback: remove header or stop Node service

---

## Phase 1: Contracts Layer (Jul 28–29, 2026) ✅

**Completed:** July 29, 2026  
**Duration:** 2 days (planned 2–3 days)

### Summary
Replaced Protocol Buffers with Zod → OpenAPI → Pydantic contract layer.

### Implementation
- **TypeScript:** `shared/ts/contracts/` — Zod schemas for all domain models
- **Python:** `shared/python/contracts/` — auto-generated Pydantic models
- **Codegen:** `make gen-contracts` → Zod → OpenAPI JSON → Pydantic
- **Schemas:** Channel, Content, Job, User, Workspace, Auth, Notification, Provider, etc.

### Benefits
- Single source of truth (Zod schemas)
- Type-safe contracts on both frontend and backend
- OpenAPI spec for documentation and validation
- No protobuf compiler, no gRPC overhead

---

## Phase 0: Freeze + ADR (Jul 27, 2026) ✅

**Completed:** July 27, 2026  
**Duration:** 1 day

### Summary
Documented decision to migrate from polyglot (Rust+Go+Python+TS) to two-language (Python+TS).

### Deliverables
- ✅ `docs/architecture/adr-004-two-language-simplification.md`
- ✅ `docs/harness/README.md`
- ✅ `MIGRATION.md` (7-phase plan)

### Rationale
- **Complexity:** 4 languages, 3 build systems, 2 RPC protocols
- **Velocity:** Rust/Go expertise bottleneck, slow iteration
- **Hiring:** Python/TS talent pool >> Rust/Go
- **Ecosystem:** Python ML/AI libraries, TypeScript frontend/backend
- **Maintenance:** Fewer dependencies, simpler CI, faster builds

### Decision
- **Keep:** Python (backend, ML, Temporal), TypeScript (frontend, gateway, streaming)
- **Remove:** Rust (gateway, harness), Go (streaming, workers, services)
- **Replace:** gRPC/protobuf → REST + Zod/Pydantic

---

## Pre-Migration Stack (Before Jul 27, 2026)

### Languages & Frameworks
- **Rust:** Axum gateway, test harness
- **Go:** Streaming hub, Temporal workers, notification dispatcher
- **Python:** AI services, Temporal activities, ML models
- **TypeScript:** Next.js dashboard, Remotion rendering

### Contracts
- Protocol Buffers (`.proto` files)
- gRPC for service-to-service communication
- Buf for protobuf management

### Pain Points
- 4 languages → 4 build systems → 4 sets of dependencies
- Protobuf schema changes required regenerating code in 3 languages
- Rust/Go expertise bottleneck for gateway/streaming changes
- Slow CI (Rust compile times, Go test coverage)
- Complex deployment (4 different runtime environments)

---

## Migration Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Languages | 4 (Rust, Go, Python, TS) | 2 (Python, TS) | -50% |
| Build systems | 4 (Cargo, Go, pip, npm) | 2 (uv, npm) | -50% |
| RPC protocols | 2 (gRPC, REST) | 1 (REST) | -50% |
| Gateway lines | 932 (Rust) | 1,200 (TS) | +29% |
| Streaming lines | 450 (Go) | 600 (TS) | +33% |
| Temporal workflows | 932 (Go) | 1,331 (Python) | +43% |
| Contract files | 45 `.proto` | 12 `.ts` Zod | -73% |
| CI duration | ~12 min | ~6 min | -50% |
| Build time (clean) | ~8 min | ~3 min | -62% |

---

## Lessons Learned

### What Went Well
- **Zod → Pydantic codegen:** Flawless. Single source of truth, type-safe on both sides.
- **Fastify:** Excellent DX, fast, Zod integration, mature ecosystem.
- **Temporal Python SDK:** Feature parity with Go SDK, better Python integration.
- **Gradual rollout:** Header-gated routers allowed instant rollback.
- **Early completion:** Finished 3 weeks ahead of schedule (4 weeks → 1 week).

### What Could Be Improved
- **Documentation lag:** ADRs and migration docs fell behind actual code changes.
- **Test coverage:** Some edge cases missed during Rust → TS port (caught in QA).
- **Temporal queue naming:** `-v2` suffix created confusion; should have used feature flags instead.

### Key Decisions
- **Keep Python for ML/AI:** No alternative with comparable ecosystem.
- **Keep TypeScript for frontend + BFF:** React/Next.js ecosystem, type safety.
- **Delete Rust/Go:** Velocity > performance for this use case.
- **REST over gRPC:** Simpler, better browser support, easier debugging.

---

## Post-Migration Stack (Current)

### Backend (Python 3.12)
- **Framework:** FastAPI (API services)
- **Workflow:** Temporal Python SDK
- **Database:** Postgres.js, SQLAlchemy (where needed)
- **Validation:** Pydantic
- **Testing:** pytest, Temporal test server
- **Linting:** ruff (format + lint)

### Frontend & BFF (TypeScript/Node 22)
- **Framework:** Next.js 15 (dashboard, marketing), Fastify 5 (gateway, streaming)
- **Validation:** Zod
- **Database:** Postgres.js
- **Testing:** Vitest, Playwright
- **Linting:** ESLint, Prettier

### Contracts
- **Source:** Zod schemas (`libs/ts/contracts/`)
- **Generated:** Pydantic models (`libs/python/contracts/`)
- **Format:** OpenAPI 3.1 JSON (intermediate)

### Infrastructure
- **Orchestration:** Docker Compose (dev), Kubernetes (prod)
- **Reverse Proxy:** Traefik
- **Database:** PostgreSQL 15 + pgvector
- **Cache:** Redis
- **Workflow:** Temporal
- **Observability:** Sentry, Prometheus, Grafana

---

## Archived Migration Docs

The following detailed migration docs have been consolidated into this changelog:

- `MIGRATION.md` (root) — 7-phase overview
- `services/temporal-workers/PHASE4_MIGRATION.md` — Temporal Go → Python
- `services/notification-dispatcher-v2/PHASE5_MIGRATION.md` — Notification dispatcher Go → Python

These files have been deleted. All migration history is preserved in this CHANGELOG.
