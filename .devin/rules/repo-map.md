# Repository Map (Phase 7 — Python + TypeScript)

Authoritative structural reference. Cross-check with `STRUCTURE.md` for
narrative detail. Any path change here MUST be reflected in `STRUCTURE.md`.

```
Autoniix/
├── .devin/                     Agent config (rules/, skills/, workflows/)
├── .github/                    Workflows (ci.yml, promote-develop-to-main.yml,
│                               versions-in-sync.yml) + branch-protection.yml
├── .husky/                     Client-side git hooks (pre-commit, pre-push)
├── backend/                    Backend services
│   ├── api/
│   │   ├── gateway/            Node/Fastify REST gateway
│   │   ├── streaming-hub/      Node SSE/WebSocket hub
│   │   └── core/               Python FastAPI microservices
│   │       ├── research/       Research + topic generation
│   │       ├── script/         Script generation
│   │       ├── voice/          TTS synthesis
│   │       ├── assets/         Stock media search
│   │       ├── thumbnail/      Thumbnail generation
│   │       ├── assembly/       Video assembly
│   │       ├── delivery/       YouTube upload
│   │       ├── analytics/      Analytics + retention
│   │       ├── admin/          Admin ops
│   │       ├── direction/      Direction generation
│   │       ├── brand/          Brand voice
│   │       ├── brain/          Adaptive decision engine (bandit + reflector)
│   │       ├── editor/         Editor operations
│   │       ├── sheets_sync/    Google Sheets sync
│   │       ├── dashboard/      Dashboard BFF
│   │       └── experiments/    A/B framework
│   ├── ai/model-server/        Python ML inference
│   ├── workers/
│   │   ├── temporal/           Temporal workflows + activities
│   │   └── notification-dispatcher/  Python notification dispatcher
│   ├── media/remotion/         Video rendering (Node + Remotion)
│   └── platform/
│       ├── resolve-finisher/   DaVinci Resolve integration
│       └── sentry-agent/       Sentry triage + auto-fix agent
├── frontend/
│   ├── dashboard/              Main dashboard (Next.js 15 + shadcn/ui)
│   └── marketing/              Landing (Next.js 15)
├── shared/
│   ├── python/                 Reusable Python (contracts, core, events,
│   │                           intelligence, llm, observability, providers,
│   │                           quality, schemas, agents)
│   └── ts/contracts/           Zod schemas (source of truth for OpenAPI)
├── infra/                      Traefik, Prometheus/Grafana/Loki, dynamic config
├── scripts/                    Build + deploy + utility scripts (ci-local.sh,
│                               apply-branch-protection.sh, run_prompt_eval.py,
│                               generate_training_data.py, trigger_first_retrain.py)
├── tools/                      Code generators (gen-pydantic.sh)
├── tests/                      Test suite (conftest.py, test_*.py,
│                               contracts/, migration/, security/, golden/,
│                               prompt_eval/, e2e/)
├── subagents/                  Subagent specifications (markdown)
├── docs/
│   └── architecture/           ADRs + design docs (adr-004 Phase 7,
│                               adr-005 harness, adr-006 branch policy,
│                               branch-protection.md, quality-gates.md, ...)
├── docker-compose.yml          All services
├── Dockerfile                  Python service base image
├── Makefile                    harness, pre-deploy, up, down, test, lint...
├── pyproject.toml              uv workspace root
├── package.json                npm workspaces (frontend/*, shared/ts/*,
│                               backend/api/gateway, backend/api/streaming-hub)
├── ruff.toml                   Two-tier lint config (blocking + aspirational)
├── versions.env                Single source of truth for all toolchain pins
├── STRUCTURE.md                Narrative structure doc
└── requirements.txt            Python dependencies
```

## Key files to know

- `shared/python/core/config.py` — All settings. Read before adding env vars.
- `shared/python/providers/registry.py` — Provider factory. Read before adding providers.
- `shared/python/core/environment.py` — is_test / is_production. Read before env-conditional code.
- `backend/workers/temporal/workers/workflows/video_production.py` — Main pipeline (13 phases).
- `scripts/init-db.sql` — All DB tables. Read before adding tables.
- `scripts/seed-data.sql` — Seed data + `system_config` keys.
- `Makefile` — Every workflow you need: `harness`, `pre-deploy`, `up`, `down`.
- `scripts/ci-local.sh` — Local mirror of GH Actions. One function per CI job.
- `.harness/` — Runtime state: reports, deploy sentinels, bypass log.

## Never write here

- `services/` at repo root — no such directory anymore.
- `libs/` at repo root — no such directory anymore.
- `apps/` at repo root — no such directory anymore.
- `rust/`, `go/`, `proto/` — Phase 7 removed them.
