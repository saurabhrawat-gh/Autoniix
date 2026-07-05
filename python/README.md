# python/ — Target Polyglot Layout Placeholder

**Status:** Placeholder (2026-07-07). Physical files still live under `src/`.

This directory exists as a target marker for **Phase D of the multi-language
backend migration** (Epic #638). It is intentionally empty except for this
README until a dedicated, tested restructure PR is merged.

## Why a placeholder?

Per ADR-001 (Polyglot Architecture), the target repo layout is:

```
autoniix/
├── rust/           # gateway + harness
├── go/             # microservices + Temporal workers  ← DONE
├── python/         # AI/ML services + agents            ← THIS DIR (target)
├── dashboard/      # Next.js frontend
├── proto/          # shared contracts
├── gen/            # generated bindings
└── tests/          # cross-cutting tests
```

Today Python code lives under `src/`. Moving it wholesale to `python/` requires
touching 222+ files (every `from src.xxx import` statement, docker-compose
service commands, Makefile targets, Dockerfiles, CI paths).

Doing that mechanical rename in a single agent session violates the "nothing
breaks" constraint because there is no in-loop way to verify the entire
Python fleet still starts under Docker.

## Deferred rename scope

The following renames are queued for a dedicated Phase D restructure PR:

| From | To | LOC impact |
|------|----|-----------|
| `src/services/brain/` | `python/brain/` | ~15 files |
| `src/services/analytics/` | `python/analytics/` | ~12 files |
| `src/services/experiments/` | `python/experiments/` | ~8 files |
| `src/services/finishing/` | `python/finishing/` | ~10 files |
| `src/services/delivery/` | `python/delivery/` (kept as legacy target of Go proxy) | ~5 files |
| `src/services/thumbnail/` | `python/thumbnail/` (kept as legacy target of Go proxy) | ~7 files |
| `src/services/voice/` | `python/voice/` (kept as legacy target of Go proxy) | ~6 files |
| `src/services/research/` | `python/research/` (kept as legacy target of Go proxy) | ~9 files |
| `src/services/script/` | `python/script/` (kept as legacy target of Go proxy) | ~8 files |
| `src/agents/critic.py` | `python/agent-critic/critic.py` | 1 file |
| `src/agents/preventor.py` | `python/agent-preventor/preventor.py` | 1 file |
| `src/intelligence/` | `python/quality-gates/` | ~20 files |
| `src/llm/embeddings.py` | `python/embeddings/embeddings.py` | 1 file |
| `src/workers/activities/brand.py` | `python/brand/brand.py` | 1 file |
| `src/workers/activities/editor.py` | `python/editor/editor.py` | 1 file |

**Everything else in `src/` stays put** (config, db, providers, workers, observability).

## Restructure script

The mechanical rename procedure is scripted at
[`scripts/phase-d-restructure.sh`](../scripts/phase-d-restructure.sh).
It is **not runnable via CI** — a human must:

1. Run it locally on a dedicated branch cut from `develop`.
2. Run the full test suite (`pytest tests/`, `docker compose up`, gateway smoke tests).
3. Update docker-compose service commands (`src.services.X.main:app` → `python.X.main:app`).
4. Update `Makefile` `SVC=` references.
5. Update Dockerfile `WORKDIR` / `COPY` paths if any hard-code `src/`.
6. Verify every microservice boots and passes health checks.
7. Merge back to `develop`.

## Why Go services already migrated but Python didn't

Go microservices were newly-written under `go/` from the start, so no rename was
needed. Python code has 6 years of `from src.xxx import yyy` accretion that
must be atomically flipped.
