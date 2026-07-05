# python/ — WRONG LOCATION — READ THIS

> **⚠️ This directory was created in error.** It reflects a superseded plan.
>
> The `python/` top-level folder is **NOT** the migration target.
>
> See [ADR-002](../docs/architecture/adr-002-monorepo-layout.md) for the locked layout.

---

## What was decided (ADR-002, locked 2026-07-05)

The repo is migrating to a **deployable-unit** layout, not a language-based one.
Python code does NOT move into a top-level `python/` folder.

**Correct target locations for Python code:**

| Current path | Target path | Type |
|-------------|------------|------|
| `src/intelligence/` | `libs/python/intelligence/` | pure lib |
| `src/quality/` | `libs/python/quality/` | pure lib |
| `src/llm/` | `libs/python/llm/` | pure lib |
| `src/events/` | `libs/python/events/` | pure lib |
| `src/providers/` | `libs/python/providers/` | pure lib |
| `src/observability/` | `libs/python/observability/` | pure lib |
| `src/schemas/` | `libs/python/schemas/` | pure lib |
| `src/{config,db,environment,flags,redis_client}.py` | `libs/python/core/` | pure lib |
| `src/agents/` | `services/agents/` | deployable service |
| `src/services/` | `services/api/` | deployable service (legacy, shrinks as Rust absorbs) |
| `src/workers/` | `services/temporal-workers/workers/` | deployable service |
| `src/temporal_workflows/` | `services/temporal-workers/workflows/` | deployable service |

The full 7-phase migration plan is in
[`scripts/phase-d-restructure.sh`](../scripts/phase-d-restructure.sh)
and [ADR-002](../docs/architecture/adr-002-monorepo-layout.md).

---

## Action required

This `python/` directory should be deleted when Phase D starts (it is an artefact
of an earlier incorrect plan). The Phase 0 skeleton script creates the correct
`libs/python/` and `services/` directories instead.
