# ADR-004: Two-Language Simplification (Python + TypeScript)

**Status:** Accepted  
**Date:** 2026-08-01  
**Decision Owners:** Saurabh Rawat (Owner), Cascade (Architect)  
**Supersedes:** ADR-001 (Polyglot Architecture)  
**Superseded By:** —

---

## Context

ADR-001 established a polyglot architecture (Rust + Go + Python + TypeScript + Protocol Buffers) designed to scale from 10 users to 1 billion users with optimal cost efficiency and performance.

After 6 weeks of implementation, we discovered that **the build complexity tax is too high for the current stage**:

1. **Build times:** 8–15 minutes for Rust cold builds vs. 30–60 seconds for Python/Node
2. **CI fragility:** 5 toolchains (Rust, Go, Python, Node, Buf) to keep in lockstep across local, act, and GitHub Actions
3. **Developer friction:** `sqlx` offline cache drift, protobuf codegen as hard prerequisite, Docker layer invalidation
4. **Premature optimization:** We are optimizing for billion-user scale at 1-user scale

The polyglot foundation was **architecturally correct** but **operationally premature**. We are collapsing back to **two languages** to prioritize **shipping velocity** over **runtime efficiency** until we have users who would notice the difference.

---

## Decision Summary

| Concern | ADR-001 (Polyglot) | ADR-004 (Two-Language) |
|---------|-------------------|----------------------|
| Backend languages | Rust + Go + Python | **Python only** |
| Frontend language | TypeScript | TypeScript (unchanged) |
| API Gateway | Rust (Axum) | **Node (Fastify)** |
| Streaming hub | Rust | **Node (Fastify + ws)** |
| Temporal workers | Go | **Python** |
| Backend services | Python | Python (unchanged) |
| Contract protocol | Protocol Buffers + Connect-RPC | **Zod + OpenAPI + REST** |
| Type safety FE↔BE | ✅ (protobuf codegen) | ✅ (Zod → TS types + Pydantic) |
| Build time (cold) | 15–20 min | **2–4 min** |
| CI complexity | 5 toolchains | **2 toolchains** |
| When to revisit | When we have 100K+ users OR p95 latency >500ms OR cost/user >$0.50 | — |

---

## Part 1: What We Keep from ADR-001

These decisions remain **locked** and unchanged:

1. **Monorepo structure** — all code in one repo, Turborepo for orchestration
2. **Temporal for workflows** — no change, just Python SDK instead of Go SDK
3. **PostgreSQL primary database** — no change
4. **Redis for cache/pubsub** — no change
5. **MinIO for object storage** — no change
6. **Observability stack** (Prometheus, Grafana, Loki, Sentry) — no change
7. **Docker Compose for dev + small deploy** — no change
8. **Trigger-based scale-out** (ADR-001 Part 11) — deferred but not deleted
9. **Microservices boundaries** (gateway, workers, services) — kept, just in different languages

---

## Part 2: New Language Boundaries

| Layer | Language | Runtime | Framework |
|-------|----------|---------|-----------|
| Dashboard (web app) | TypeScript | Node 22 | Next.js 15 |
| Marketing site | TypeScript | Node 22 | Next.js 15 |
| **API Gateway / BFF** | **TypeScript** | Node 22 | **Fastify 5** |
| **Streaming hub** | **TypeScript** | Node 22 | **Fastify + ws** |
| All backend services | Python 3.12 | Python | FastAPI |
| **Temporal workflows** | **Python 3.12** | Python | **temporalio SDK** |
| **Temporal workers** | **Python 3.12** | Python | **temporalio SDK** |
| AI / agents / brain | Python 3.12 | Python | FastAPI |
| Remotion renderer | TypeScript | Node 22 | Remotion |

**Deleted languages:** Rust, Go.  
**Deleted tooling:** Cargo, rustc, go, buf, protoc.

---

## Part 3: Contract Layer — Zod + OpenAPI

**Problem with Protocol Buffers:**
- Requires `buf` toolchain + `protoc` plugins for 4 languages
- Breaking change detection via `buf breaking` only works if all `.proto` files are perfectly maintained
- Codegen must run before every build in every language
- One broken `.proto` → all 4 languages fail to build

**Solution: Zod as source of truth**

```
shared/ts/contracts/
├── src/
│   ├── channel.schema.ts       # export const ChannelSchema = z.object({...})
│   ├── content.schema.ts
│   ├── job.schema.ts
│   └── index.ts                # re-export all + OpenAPI spec generator
├── package.json
└── tsconfig.json

Generated outputs:
1. TypeScript types (via z.infer<typeof ChannelSchema>)
2. OpenAPI 3.1 JSON (via @asteasolutions/zod-to-openapi)
3. Python Pydantic models (via datamodel-code-generator reading OpenAPI)
```

**Why Zod:**
- TypeScript-native, no external codegen needed for TS consumers
- Runtime validation + compile-time types in one definition
- `zod-to-openapi` generates perfect OpenAPI 3.1 specs
- `datamodel-code-generator` generates Pydantic v2 models from OpenAPI
- Breaking changes detected by TypeScript compiler (field renames, type changes)

**Contract flow:**
```
1. Developer edits shared/ts/contracts/src/channel.schema.ts
2. TypeScript compiler validates Zod schema
3. make gen-contracts runs:
   - Exports OpenAPI JSON to shared/ts/contracts/openapi.json
   - Runs datamodel-code-generator → shared/python/contracts/
4. Python services import from shared.python.contracts
5. TypeScript services import from @autoniix/contracts
```

---

## Part 4: API Surface — REST + JSON

**Frontend ↔ Gateway:** REST + JSON over HTTP/1.1 or HTTP/2

- Endpoints follow `/api/v2/{resource}` pattern (existing)
- Request/response validated against Zod schemas
- OpenAPI spec auto-generated and served at `/api/v2/openapi.json`
- Type-safe clients in dashboard via `openapi-typescript` or direct Zod inference

**Gateway ↔ Backend services:** HTTP + JSON (FastAPI to FastAPI)

- Internal services expose FastAPI apps with Pydantic models
- Gateway calls them via `httpx` (async HTTP client)
- No gRPC, no protobuf serialization overhead
- Service discovery via environment variables (simple, works in Docker Compose)

**Streaming:** Server-Sent Events (SSE) for one-way, WebSocket for bidirectional

- SSE for progress updates, notifications (simpler than WebSocket, auto-reconnect in browsers)
- WebSocket only where bidirectional is required (chat, collaborative editing)
- Both handled by Fastify in `apps/streaming-hub`

---

## Part 5: Repository Structure (Target State)

```
autoniix/
├── apps/
│   ├── dashboard/              # Next.js (existing, unchanged)
│   ├── marketing/              # Next.js (existing, unchanged)
│   ├── gateway/                # NEW — Fastify BFF (replaces services/gateway Rust)
│   └── streaming-hub/          # NEW — Fastify WS/SSE (replaces Rust streaming)
│
├── services/                   # ALL Python from here down
│   ├── api/                    # FastAPI monolith (existing)
│   ├── brain/                  # FastAPI (existing)
│   ├── agents/                 # FastAPI (existing)
│   ├── workers/                # Temporal workers (Python, existing but needs update)
│   ├── research/               # NEW — FastAPI (was planned as Go in ADR-001)
│   ├── script/                 # NEW — FastAPI
│   ├── voice/                  # NEW — FastAPI
│   ├── thumbnail/              # NEW — FastAPI
│   ├── delivery/               # NEW — FastAPI
│   ├── analytics/              # FastAPI (existing)
│   ├── finishing/              # FastAPI (existing)
│   └── remotion/               # Node (existing, unchanged)
│
├── shared/
│   ├── ts/
│   │   ├── contracts/          # NEW — Zod schemas + OpenAPI export
│   │   ├── ui/                 # Shared React components (existing)
│   │   ├── config/             # Shared eslint/tsconfig/prettier
│   │   └── testing/            # Shared vitest/playwright helpers
│   └── python/
│       ├── contracts/          # NEW — Generated Pydantic models
│       ├── core/               # Existing
│       ├── events/             # Existing
│       ├── intelligence/       # Existing
│       └── testing/            # NEW — pytest fixtures + factories
│
├── infra/                      # Migrations, observability, Caddy (existing)
├── tools/                      # Scripts, codegen
├── tests/                      # Top-level e2e + contract tests
├── docs/
│   ├── architecture/           # ADRs
│   └── harness/                # NEW — standardization docs
│
├── .github/workflows/          # CI (will be rewritten)
├── docker-compose.yml          # Dev stack (will be updated)
├── Makefile                    # Build commands (will be updated)
├── package.json                # Root package.json (will be updated for pnpm)
├── pnpm-workspace.yaml         # NEW — pnpm workspaces
├── pyproject.toml              # NEW — uv workspace root
├── turbo.json                  # Turborepo config (existing, will be updated)
└── versions.env                # Tool versions (will be simplified)
```

**Deleted:**
- `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`
- `go.mod`, `go.sum`, `.go-version`
- `proto/` (entire directory)
- `gen/go/` (generated Go code)
- `services/gateway/` (Rust)
- `services/harness/` (Rust)
- `.golangci.yml`, `rustfmt.toml`

---

## Part 6: Standardization Harness

### 6.1 Python Stack

| Concern | Tool | Config |
|---------|------|--------|
| Package manager | **uv** (10-100× faster than pip) | `pyproject.toml` workspace |
| Formatter | **Ruff format** | `ruff.toml` |
| Linter | **Ruff** (replaces flake8, isort, pylint, bandit) | `ruff.toml` |
| Type checker | **mypy --strict** (libs) + **basedpyright** (services) | `pyproject.toml` |
| Test runner | **pytest** + asyncio + cov + xdist | `pytest.ini` |
| DB tests | **testcontainers-python** | — |
| Migrations | **alembic** | `alembic.ini` |

**Ruff config:**
```toml
target-version = "py312"
line-length = 100
select = ["E","F","W","I","N","D","UP","B","C4","SIM","TCH","PT","RET","ARG","PL","RUF","S","ASYNC"]
ignore = ["D100","D104","PLR0913"]
[per-file-ignores]
"tests/**" = ["S101","D","PLR2004","ARG"]
```

### 6.2 TypeScript Stack

| Concern | Tool | Config |
|---------|------|--------|
| Package manager | **pnpm** (3× faster than npm) | `pnpm-workspace.yaml` |
| Build orchestrator | **Turborepo** | `turbo.json` |
| Formatter | **Prettier 3** | `.prettierrc.json` |
| Linter | **ESLint 9 flat config** | `eslint.config.mjs` |
| Type checker | **tsc --noEmit --strict** | `tsconfig.base.json` |
| Unit tests | **Vitest** | `vitest.config.ts` |
| E2E tests | **Playwright** | `playwright.config.ts` |
| API mocking | **MSW** | — |

**TypeScript strict config:**
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true
  }
}
```

### 6.3 Import Rules (Enforced by Linters)

**Python:**
1. Absolute imports only, no relative imports across service boundaries
2. Order: stdlib → third-party → `libs.*` → `services.<self>.*` → local
3. No cross-service imports (enforced by `tach`)
4. `libs.python.contracts` is the only shared package

**TypeScript:**
1. No default exports except React components + Next.js pages
2. `import type` mandatory for type-only imports
3. Path aliases only: `@autoniix/contracts`, `@autoniix/ui`, etc.
4. No circular imports (enforced by `eslint-plugin-import`)

### 6.4 Testing Layers

| Layer | Python | TypeScript | Coverage floor |
|-------|--------|------------|----------------|
| Unit | pytest | Vitest | **80%** |
| Integration | pytest + testcontainers | Vitest + testcontainers | 60% |
| Contract | pytest vs OpenAPI | Vitest vs Zod | 100% |
| E2E | — | Playwright | Critical flows |

---

## Part 7: CI Pipeline (New)

Replace 6 workflows with **3**:

**`ci.yml`** — runs on every PR (~4–6 min):
```yaml
jobs:
  install:
    - uv sync
    - pnpm install
  
  lint:
    - ruff check
    - eslint
    - prettier --check
  
  typecheck:
    - mypy
    - basedpyright
    - tsc --noEmit
  
  test:
    - pytest (parallel)
    - vitest (parallel)
  
  contract:
    - schema round-trip validation
  
  build:
    - docker buildx (all images, cached)
  
  e2e:
    - docker compose up
    - playwright
  
  coverage:
    - codecov (fail if diff < 80%)
```

**`release.yml`** — on merge to `main`:
- Tag images with git SHA
- Push to registry
- Trigger deploy

**`nightly.yml`** — dependency audit, visual diff

---

## Part 8: Migration Plan (7 Phases)

| Phase | Duration | Deliverable | Risk |
|-------|----------|-------------|------|
| **0. Freeze + ADR** | 1 day | This document + freeze polyglot work | None |
| **1. Contracts** | 2–3 days | `libs/ts/contracts` + `libs/python/contracts` | Low |
| **2. Gateway** | 5–7 days | Node Fastify BFF, feature-flagged at Caddy | Low (rollback = flip flag) |
| **3. Streaming** | 2 days | Node WS/SSE service | Low |
| **4. Temporal** | 3–4 days | Python workers (revive existing) | Low (keep Go workers idle) |
| **5. Services** | 5–7 days | Python FastAPI for research/script/voice/etc | Low |
| **6. Delete** | 1 day | Remove Rust/Go/proto | Low (git revert) |
| **7. Standardize** | 3–4 days | Apply lint/format/test rules, green CI | Low |

**Total: ~4 weeks**

Each phase is independently shippable. Rollback at any phase is trivial.

---

## Part 9: What We Lose (And Why It's OK)

| ADR-001 Benefit | Lost? | Why It's OK Now |
|----------------|-------|-----------------|
| 50× cost efficiency at scale | ✅ Yes | We have 1 user, not 1M users |
| Millisecond cold starts | ✅ Yes | Docker Compose, not serverless |
| Compile-time SQL verification | ✅ Yes | Tests + migrations catch SQL errors |
| Sub-10ms p50 latency | ✅ Yes | Current p50 is ~80ms, users don't notice |
| Memory footprint (20MB vs 200MB) | ✅ Yes | VPS has 16GB RAM, not a constraint |
| Type safety across wire | ❌ **Kept** | Zod + OpenAPI gives same guarantee |
| Microservices boundaries | ❌ **Kept** | Same boundaries, different languages |
| Temporal workflows | ❌ **Kept** | Python SDK is mature |
| Observability | ❌ **Kept** | Unchanged |
| Scale-out triggers | ❌ **Kept** | Deferred, not deleted |

---

## Part 10: When to Revisit This Decision

We will **revert to ADR-001** (or a hybrid) when **any** of these triggers fire:

1. **100K+ active users** — Python GIL becomes a bottleneck
2. **p95 API latency >500ms** sustained for 1 week — need Rust hot paths
3. **Cost per user >$0.50/month** — need Go/Rust efficiency
4. **First multi-region deployment** — need CockroachDB + service mesh (ADR-001 Part 5)
5. **First mobile app** — might want native gRPC clients (Connect-Swift/Kotlin)
6. **Kubernetes migration** — might want Go for k8s operators

Until then, **Python + TypeScript is the correct choice** because:
- Faster builds = faster shipping
- Simpler CI = fewer broken builds
- 2 languages = easier onboarding
- Python ecosystem = best for AI/ML (our core value)

---

## Part 11: Quality Gates (Hard CI Blocks)

A PR **cannot merge** if:
1. Any linter error (ruff, eslint)
2. Any format diff (ruff format, prettier)
3. Any type error (mypy, basedpyright, tsc)
4. Any test failure
5. Diff coverage <80%
6. `pip-audit` or `npm audit` high/critical
7. Bundle size regression >10%
8. OpenAPI breaking change without `BREAKING-CHANGE:` trailer

---

## Part 12: Tool Versions (Simplified)

**`versions.env` v2:**
```
NODE=22.23.1
NPM=10.9.8
PNPM=9.15.0
PYTHON=3.12.7
POSTGRES=pg15
```

Managed by **mise** (`.mise.toml`).

**Deleted:** Rust, Go, Buf pins.

---

## Part 13: Makefile Targets (Final)

```makefile
make setup            # uv sync + pnpm install + mise install
make gen-contracts    # zod -> openapi -> pydantic
make lint             # ruff + eslint + prettier check
make fmt              # ruff format + prettier write
make typecheck        # mypy + basedpyright + tsc
make test             # pytest + vitest
make test-e2e         # playwright
make build            # docker buildx all images
make up               # docker compose up
make down             # docker compose down
make ci-fast          # lint + typecheck + unit (pre-push)
make ci               # full CI locally
make verify-versions  # versions.env parity
make ship             # merge develop -> main
```

---

## Part 14: Anti-Patterns We Avoid

1. **Premature optimization** — we optimized for billion-user scale at 1-user scale (ADR-001's mistake)
2. **Technology for technology's sake** — Rust/Go are amazing, but not needed yet
3. **Build complexity over shipping velocity** — 15-min builds blocked us from shipping
4. **Multiple sources of truth** — Zod is the contract, everything derives from it
5. **Cross-service imports** — enforced by linters
6. **Skipping tests** — 80% diff coverage is a hard gate

---

## Part 15: Success Criteria

This ADR is **successful** if, 4 weeks from now:

1. ✅ Zero Rust/Go/protobuf code in the repo
2. ✅ CI runs in <6 minutes (vs current 20+ min)
3. ✅ All tests green
4. ✅ 80%+ code coverage
5. ✅ Zero linter/formatter/type errors
6. ✅ `make ci` passes locally in <10 min
7. ✅ Docker builds in <2 min (vs current 15 min)
8. ✅ All existing features work (no regressions)

---

## Approval

- **Architect (Cascade):** ✅ Approved 2026-08-01
- **Owner (Saurabh Rawat):** ✅ Approved 2026-08-01

This ADR **supersedes ADR-001** for the current stage (1–10K users). ADR-001's scale-out triggers (Part 11) are **deferred, not deleted**. When triggers fire, we will implement a **hybrid** approach (Python + TypeScript + Rust hot paths) rather than full polyglot.

---

## Appendix A: Build Time Comparison

| Task | ADR-001 (Polyglot) | ADR-004 (Two-Lang) | Speedup |
|------|-------------------|-------------------|---------|
| Cold build (all services) | 15–20 min | 2–4 min | **5×** |
| Incremental build | 3–5 min | 30–60 sec | **4×** |
| CI (full) | 20–25 min | 4–6 min | **4×** |
| Docker image (gateway) | 8–12 min | 45–60 sec | **10×** |
| Pre-commit hook | 15–30 sec | 5–10 sec | **2×** |

---

## Appendix B: Deleted Files (Post-Phase 6)

```
Cargo.toml, Cargo.lock, rust-toolchain.toml
go.mod, go.sum, .go-version
proto/ (entire directory)
gen/go/ (entire directory)
services/gateway/ (Rust)
services/harness/ (Rust)
.golangci.yml
rustfmt.toml
.github/workflows/rust-*.yml
.github/workflows/go-*.yml
.github/workflows/proto-*.yml
```

Total lines deleted: **~50K LOC** (Rust + Go + protobuf)

---

**End of ADR-004**
