# CLAUDE.md — YouTube Automation
# Last audited: 2025-05-03

---

## Project Identity

Self-hosted YouTube content automation system. Temporal microservices orchestrate a 13-phase video production pipeline: research → script → voice → assets → thumbnail → assembly → render → delivery → analytics. Python FastAPI backend, Next.js dashboard, Remotion (TypeScript) rendering. Local-first intelligence (spaCy, sklearn, NLTK) with LLM fallback.

Tech stack: Python 3.11, FastAPI, Temporal, PostgreSQL (pgvector), Redis, MinIO, Next.js 14, Remotion v3, Docker
Repo owner: saurabhrawat-gh

---

## Architecture Rules

- Services communicate via HTTP only (Docker network). No shared DB access across services.
- Workers handle Temporal protocol. Services handle business logic. Never cross.
- Provider pattern (ABC + ProviderRegistry) for all external APIs: LLM, TTS, Image, Search, Storage.
- Intelligence modules are local-first ($0.00 cost). LLM is fallback only.
- Budget guard on every LLM call. `accrued + estimated > max` → abort.
- 10 microservices on ports 5001-5009, 8012-8013. Dashboard on 3000/8020. Remotion on 4000.

---

## Naming Conventions

- Files: `snake_case.py`
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Provider ABC: `<Category>Provider`, concrete: `<Name><Category>`
- Registry key: `category.name` (e.g., `llm.script`)
- Temporal workflows: `PascalCaseWorkflow`, activities: `snake_case`
- DB tables: `snake_case` plural, columns: `snake_case`
- Content IDs: `VID_<CHANNEL>_<DATE>_<SEQ>`, test: `TEST_VID_*`
- Import: `from __future__ import annotations` at top of every file

---

## Repo Map

```
src/config.py              All settings (read before adding env vars)
src/providers/             Provider abstraction (ABC + Registry)
src/services/              Business logic microservices (16 services)
src/temporal_workflows/    Temporal workflow definitions
src/workers/               Temporal worker entry points
src/schemas/               Pydantic models (VideoParams, VideoResult)
src/environment.py         Test vs Production mode
tests/                     pytest suite
scripts/                   init-db.sql, seed-data.sql, training data
dashboard/                 Next.js 14 frontend
docs/                      Architecture docs (00-11)
docker-compose.yml         All services (~21 containers)
```

---

## Test Expectations

- Write tests for: providers, intelligence modules, API endpoints, environment mode
- Framework: pytest + pytest-asyncio
- Run: `pytest`
- Coverage: 70%+ overall, 80%+ for intelligence modules
- Use `mock_pool`/`FakeRecord` fixtures from conftest.py
- Mock external APIs — never call real APIs in tests

---

## Commands

```bash
dev:    docker compose up -d
test:   pytest
lint:   ruff check src/ tests/
build:  docker compose build
```

---

## Karpathy Behavioral Rules

- **THINK FIRST:** State assumptions explicitly. If ambiguous, ask — never guess forward.
- **STAY SIMPLE:** Minimum code that solves the problem. No speculative abstractions.
- **STAY SURGICAL:** Touch only what the task requires. Match existing style.
- **SET GOALS:** Transform tasks into verifiable success criteria. Loop until verified.

---

## Safety Rules

- Never hardcode secrets or API keys
- Never write to production DB without dry-run confirmation
- Read before write — always read current file state before editing
- Verify before commit — confirm paths, imports, and signatures exist
- If git status is not clean before a Write operation, stash first
- Budget guard on every LLM call — never skip
- Delivery blocks YouTube upload in test mode

---

## LLM/Code Boundary

Use LLM for: classification, drafting, summarization, judgment calls, creative generation.
Use plain code for: routing, fetching, filtering, sorting, scheduling, validation, retry logic, budget checks.

---

## Context Hygiene

- For tasks reading more than 10 files: delegate to a subagent
- Inject State Card at session start rather than replaying conversation
- Do not paste full file contents — use file references and read on demand
