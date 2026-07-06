# ADR-002: Monorepo Layout — Deployable-Unit Structure

**Status:** 🔒 LOCKED  
**Date:** 2026-07-05  
**Deciders:** Saurabh Rawat (owner)  
**Supersedes:** ADR-001 §4 (which proposed a language-based layout: `rust/`, `go/`, `python/`)  
**Related:** ADR-003 (migration sequencing — Phase D references this ADR)  
**Source plan:** `~/.windsurf/plans/monorepo-layout-9dc209.md`

---

## Context

ADR-001 proposed grouping code by language at the top level:
```
rust/   go/   python/   frontend/
```

This is simpler to start with but breaks down in practice:
- A "Python service" that embeds a Go sidecar lives in two subtrees.
- Adding a new language forces a top-level folder, not a service entry.
- Monorepo tooling (Turborepo, Bazel, Nx) works on **deployable units**, not language folders.
- `deploy gateway` ↔ `services/gateway/` is a 1:1 mapping; `deploy gateway` ↔ `rust/gateway/` requires knowing the language first.

**Decision:** Replace the language-based layout with a **deployable-unit** layout.

---

## Decision

**Target layout:**

```
autoniix/
│
├── apps/                          # user-facing browser apps
│   ├── dashboard/                 # ← dashboard/       (Next.js operator dashboard)
│   └── marketing/                 # ← web/             (Next.js marketing site)
│
├── services/                      # deployable processes (any language)
│   ├── gateway/                   # ← rust/gateway/    (Rust Axum BFF)
│   ├── harness/                   # ← rust/harness/    (Rust test harness)
│   ├── streaming-hub/             # ← go/streaming-hub/
│   ├── notification-dispatcher/   # ← go/notification-dispatcher/
│   ├── service-delivery/          # ← go/service-delivery/
│   ├── service-thumbnail/         # ← go/service-thumbnail/
│   ├── service-voice/             # ← go/service-voice/
│   ├── service-research/          # ← go/service-research/
│   ├── service-script/            # ← go/service-script/
│   ├── temporal-workers/          # ← go/worker/* (production + scheduler)
│   ├── agents/                    # ← src/agents/      (LangGraph agents)
│   └── api/                       # ← src/services/    (Python FastAPI — legacy, shrinks as Rust absorbs)
│
├── libs/                          # pure code, no process — imported by services/apps
│   ├── go/
│   │   └── shared/                # ← go/shared/
│   ├── python/
│   │   ├── intelligence/          # ← src/intelligence/
│   │   ├── quality/               # ← src/quality/
│   │   ├── llm/                   # ← src/llm/
│   │   ├── events/                # ← src/events/
│   │   ├── providers/             # ← src/providers/
│   │   ├── observability/         # ← src/observability/
│   │   ├── schemas/               # ← src/schemas/
│   │   └── core/                  # ← src/{config,db,environment,flags,redis_client}.py
│   └── sdk/
│       └── python/                # ← sdk/python/
│
├── proto/                         # unchanged — shared gRPC/Connect contracts
├── gen/                           # generated bindings (go committed; others gitignored)
│
├── infra/
│   ├── traefik/                   # ← traefik/
│   ├── caddy/                     # ← Caddyfile
│   ├── observability/             # ← observability/
│   ├── migrations/                # ← scripts/migrations/
│   └── config/                    # ← config/
│
├── tools/
│   ├── cleanup/                   # ← scripts/cleanup/
│   ├── migration/                 # ← scripts/migration/
│   ├── seeds/                     # ← scripts/seeds/
│   └── scripts/                   # ← remaining loose scripts/*
│
├── docs/                          # unchanged
├── tests/                         # stays at root (cross-cutting integration/e2e)
│
│   (root-only files — NEVER move these)
├── docker-compose.yml             # muscle memory + tool discovery
├── Makefile
├── package.json / turbo.json
├── pytest.ini / requirements.txt
└── Cargo.toml                     # workspace root (members rewritten to services/gateway etc.)
```

---

## Key differences from ADR-001 §4

| Concern | ADR-001 (superseded) | ADR-002 (this ADR) |
|---------|---------------------|--------------------|
| Top-level grouping | Language (`rust/`, `go/`, `python/`) | Deployable unit (`apps/`, `services/`, `libs/`) |
| Adding a new language | New top-level folder | New service entry inside existing tree |
| Shared lib code | `go/shared/`, `python/` (flat) | `libs/go/shared/`, `libs/python/<pkg>/` |
| Python AI/ML services | `python/brain/`, `python/analytics/` etc. | `services/api/` (running); `libs/python/intelligence/` etc. (pure lib) |
| Frontend apps | `dashboard/`, `web/` at root | `apps/dashboard/`, `apps/marketing/` |
| Infra/scripts | `traefik/`, `observability/`, `scripts/` at root | `infra/`, `tools/` |

---

## Open questions (resolve before Phase 1 starts)

1. **Python package naming in `libs/python/`:** Keep short names (`intelligence`) or namespace (`autoniix_intelligence`)? Short names = fewer import changes. Namespace = safer against PyPI collisions. **Recommendation: short names, no import churn.**
2. **Go module root:** Single `go.mod` at repo root (`module github.com/saurabhrawat-gh/autoniix`) or keep multi-module under `libs/go/`? **Recommendation: single root `go.mod`.**
3. **`services/api/` fate:** Is `src/services/` (Python FastAPI legacy) still active, or fully replaced by Rust gateway? If fully replaced at Phase D time, skip the move and delete it in Phase 4b instead.
4. **`docker-compose.yml` location:** Stays at root. Only `build.context` paths inside it change.

---

## Migration phases (from `monorepo-layout-9dc209.md`)

Executed as Phase D of ADR-003 sequencing. Each phase is one branch, one merge, fully revertable.

| Phase | Name | Blast radius | Risk |
|-------|------|-------------|------|
| 0 | ADR + skeleton (this ADR + empty dirs) | ~5 files | none |
| 1 | `apps/` — move dashboard + web | ~15 files | low |
| 2 | `services/` — move Rust gateway + harness | ~20 files | low |
| 3 | Verify existing polyglot services | ~5 files | none |
| 4a | `libs/python/` — split pure Python src | ~200 files (imports) | **medium** |
| 4b | `services/` — split Python running processes | ~40 files | medium |
| 5 | `libs/go/` + `libs/sdk/` | ~10 files | low |
| 6 | `infra/` + `tools/` | ~30 files | low |
| 7 | Docs + final grep cleanup | ~40 files | low |

**Exit criteria (Phase 7):**  
`rg 'src/|rust/|dashboard/|web/|go/shared|sdk/python' -l` returns nothing outside this ADR and `docker-compose.yml`.

---

## Execution rule

Every phase MUST:
1. Be a dedicated branch cut from `develop`.
2. Contain ONLY `git mv` + path-string edits — zero logic changes.
3. Pass `bash scripts/ci-local.sh --full` before merge.
4. Merge as `chore(phase-d-N): <name>` via local `--no-ff` merge (no PRs per repo rule).
5. Remain independently revertable: `git revert <merge-commit>`.

**Start date:** After build freeze lifts (2026-07-11). Phase 0 (skeleton + this ADR) may land on `develop` during the freeze since it is documentation-only (zero code moves).

---

## Reversal

Each phase can be reverted independently with `git revert <merge-commit>`. Phases don't touch each other's file sets (except Phase 0 which creates the skeleton directories every other phase depends on — revert Phase 0 only if all later phases are also reverted first).
