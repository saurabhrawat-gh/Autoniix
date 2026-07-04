# ADR-003: Migration Sequencing — Harness → Rust → Go → Directory Restructure

**Status:** 🔒 LOCKED
**Date:** 2026-07-04
**Deciders:** Saurabh Rawat (owner)
**Supersedes:** — (extends ADR-001 with an execution sequence)
**Related:** ADR-001 (polyglot architecture), HARNESS-ENGINEERING-PLAN.md (v4), HARNESS-LANGUAGE-DECISION.md

---

## Context

Three simultaneous migrations are open in the codebase, each at different completion levels:

| Migration | Completion | Remaining scope |
|---|---:|---|
| Python → Rust (gateway) | ~34% | 176 endpoints in `dashboard/api/*.py` |
| Python → Go (services + workflows) | 0% | 11 services, ~14,000 LOC |
| Directory restructure | 0% | 7-phase `git mv` sweep per `monorepo-layout-9dc209.md` |
| Harness completion | ~50% | 7 stories, ~2 weeks (IM-187 Epic) |

Prior verbal plan was: *migrate everything first, then restructure, then harness.* This order was inverted for the harness — HARNESS-ENGINEERING-PLAN.md v4 explicitly locks harness-first because migrating ~14,000 LOC without automated parity gates carries unacceptable production-bug risk (§Executive Summary).

## Decision

**Execute migrations in this locked order:**

```
Phase A: Finish the harness       (~2 weeks)   — Epic IM-187
Phase B: Finish Rust migration    (~8–10 weeks) — Epic TBD
Phase C: Execute Go migration     (~24–28 weeks) — Epic TBD
Phase D: Directory restructure    (~1 week)    — Epic TBD
```

**Total: ~9–10 months sequential, ~8 months with light overlap.**

Attached rule: **no migration PR merges without the harness parity check green.** This is the whole point of putting Phase A first.

## Rationale

### Why harness first
- The harness is a **parity-testing scaffold** that proves `Python ≡ Rust ≡ Go` output-for-output. Its purpose is to run *during* migration, gating every PR in CI.
- Migrating 14,000 LOC of Python → Go first, then discovering behavioral drift, forces one of: roll back weeks of work, ship the bugs, or freeze production.
- ~50% of the harness (~3,258 LOC) already exists in `rust/harness/` and `go/shared/testharness/`. Finishing the remaining ~50% (~2 weeks) is a small upfront cost for months of downstream safety.
- Explicit quote from HARNESS-ENGINEERING-PLAN.md v4 §Executive Summary: *"Build harness infrastructure FIRST (3-4 weeks), then migrate with confidence."*

### Why Rust before Go
- Rust owns the gateway (frontend-facing). Every day of Python v2 endpoint drift is a day of frontend API churn.
- Go owns backend services (downstream of gateway). Independent of frontend.
- Rust is 34% done; Go is 0% done. Finishing the closer-to-done migration first frees mental bandwidth for the larger effort.

### Why directory restructure last
- By the time Rust + Go are complete, every service that will ever exist has been created.
- One clean `git mv` sweep instead of moving files that don't exist yet (or moving files twice).
- The target layout in `monorepo-layout-9dc209.md` locks the finished architecture, not a moving target.

### Why NOT harness last
- Harness is not a nice-to-have test suite you write after shipping. It is the safety net that lets migration cutovers happen without regressions.
- Post-hoc harness makes sense only when rewriting from scratch with no reference implementation. We have a live Python system defining "correct behavior" — the harness must prove match to it *during* migration, not after.

## Consequences

### Positive
- Every migration PR ships behind an automated parity gate — regression bugs caught in CI, not production.
- Provider API credits saved in test ($500/week per HARNESS-PLAN §2).
- Frontend can consume Rust gateway with confidence after Phase B, unblocking product work while Go migration runs long.
- Single directory restructure at the end = zero rework.

### Negative
- ~2 weeks of upfront harness work before any Phase B migration lands.
- Total sequential timeline is ~9–10 months — longer than any prior estimate.
- Directory restructure delays mean the current `src/`, `rust/`, `dashboard/`, `web/`, `go/` layout persists throughout the migration period.

### Neutral
- Small parallelism possible: `providers.py` migration (biggest Phase B chunk, 22% of v2) can begin integrating against the harness in the last week of Phase A, shaving ~3 weeks off total time.

## Phase A — Harness completion (2 weeks)

**Epic:** IM-187 / GH #704
**Stories:** IM-188 through IM-194 / GH #705 through #711

| Story | Description | Priority |
|---|---|---|
| A1 (IM-188 / #705) | OpenAPI schema generation via utoipa | Critical |
| A2 (IM-189 / #706) | Provider-mock injection (`PROVIDER_MODE=mock`) | Critical |
| A3 (IM-190 / #707) | Reusable `GatewayHarness` fixture | High |
| A4 (IM-191 / #708) | Golden-file regression suite (74 endpoints × 3 inputs) | Critical |
| A5 (IM-192 / #709) | CI blocking gate + required check | Critical |
| A6 (IM-193 / #710) | Criterion benchmarks + 10% perf regression gate | High |
| A7 (IM-194 / #711) | Go harness template (forward-looking for Phase C G0) | Medium |

**Exit criteria:**
- `cargo test -p harness` green in CI
- Every currently-migrated endpoint has ≥1 passing golden file vs Python v2
- `PROVIDER_MODE=mock` = zero external API calls in test
- Perf regression gate active
- Branch protection: `equivalence` required on `develop` + `main`
- `HARNESS-ENGINEERING-PLAN.md` bumped to v5

## Phase B — Rust migration completion (8–10 weeks)

**Order (from `python-to-rust-migration-status-9dc209.md`):**
1. `providers.py` — 49 endpoints (3–4 weeks)
2. `workspace.py` remainder — 26 endpoints (1–2 weeks)
3. `library` cluster — 27 endpoints (2 weeks)
4. `jobs.py` — 11 endpoints (1 week)
5. `review` cluster — 14 endpoints (1 week)
6. Remainder — ~33 endpoints (2 weeks)

**Exit criteria:** 100% of v2 endpoints served by Rust gateway. Python v2 dashboard code deleted. `dashboard/main.py` (v1) deleted.

## Phase C — Go migration execution (24–28 weeks)

**Order (from `python-to-go-migration-status-9dc209.md`):**
- G0: Foundation (go.work, proto bindings, db, telemetry) — 1 week
- G1: `notification-dispatcher` — 1 week (smallest, safest)
- G2: `streaming-hub` — 1–2 weeks
- G3: `service-delivery` — 2 weeks
- G4: `service-thumbnail` — 2–3 weeks
- G5: `service-voice` — 2–3 weeks
- G6: `service-research` — 4–5 weeks
- G7: `service-script` — 5–6 weeks (largest)
- G8: `temporal-worker-production` — 4–6 weeks (versioning safety)
- G9: `temporal-worker-scheduler` — 3–4 weeks

**Exit criteria:** 100% of ADR-001 §2.2 Go services running in production. All corresponding Python code deleted.

## Phase D — Directory restructure (1 week)

Per `monorepo-layout-9dc209.md`. Seven small phases, each a pure `git mv`.

**Exit criteria:** `rg 'src/|rust/|dashboard/|web/|go/shared|sdk/python' -l` returns nothing outside this ADR.

## Enforcement

**In CI:**
- `.github/workflows/equivalence.yml` runs Python↔Rust parity on every PR touching `rust/gateway/**` — required check on `develop` and `main`.
- `.github/workflows/build.yml` includes `harness-contract`, `harness-providers`, `bench-regression` — all required checks.

**In workflows:**
- `.devin/workflows/dev-agent.md` updated after Phase A: **new endpoints must be implemented in Rust only** (freeze Python v2 additions).
- `.devin/workflows/pre-commit.md` includes `cargo test -p harness` in local validation.

## Review triggers

Revisit this ADR if:
- Any phase exceeds its estimate by > 50% (re-plan).
- A hard product deadline forces skipping the harness (document the deviation, plan retroactive coverage).
- ADR-001 (polyglot architecture) changes.

## References

- `docs/architecture/ADR-001-polyglot-architecture.md`
- `docs/architecture/HARNESS-ENGINEERING-PLAN.md` (v4)
- `docs/architecture/HARNESS-LANGUAGE-DECISION.md`
- Plan artifacts:
  - `/Users/saurabhrawat/.windsurf/plans/migration-sequencing-correction-9dc209.md`
  - `/Users/saurabhrawat/.windsurf/plans/phase-a-harness-execution-9dc209.md`
  - `/Users/saurabhrawat/.windsurf/plans/python-to-rust-migration-status-9dc209.md`
  - `/Users/saurabhrawat/.windsurf/plans/python-to-go-migration-status-9dc209.md`
  - `/Users/saurabhrawat/.windsurf/plans/monorepo-layout-9dc209.md`
- Tickets:
  - Epic IM-187 / GH #704
  - Stories IM-188 through IM-194 / GH #705 through #711
