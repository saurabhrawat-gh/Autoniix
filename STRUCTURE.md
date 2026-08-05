# Repository Structure

This document describes the current directory structure of the Autoniix monorepo after the Phase 7 cleanup and restructure (August 2026).

## Top-Level Layout

```
Autoniix/
├── frontend/          # Frontend applications (Next.js)
├── backend/           # Backend services (Python + TypeScript)
├── shared/            # Shared code (contracts, providers, intelligence)
├── infra/             # Infrastructure configs (Traefik, observability)
├── scripts/           # Build, deploy, and utility scripts
├── tools/             # Development tools and generators
├── .devin/            # Devin/Windsurf workflows
├── subagents/         # Subagent configurations
└── docs/              # Architecture docs and ADRs
```

## Frontend (`frontend/`)

Next.js applications for user-facing interfaces.

```
frontend/
├── dashboard/         # Main dashboard (Next.js 15 + shadcn/ui)
│   ├── src/app/       # App router pages
│   ├── src/components/# React components
│   ├── src/lib/       # Utilities, hooks, API client
│   └── src/stories/   # Storybook stories
└── marketing/         # Landing page (Next.js 15)
    ├── src/app/       # Marketing pages
    └── src/components/# Marketing components
```

## Backend (`backend/`)

Backend services organized by function into 5 categories.

### 1. API Services (`backend/api/`)

HTTP/WebSocket services for client communication.

```
backend/api/
├── gateway/           # Fastify REST API (Node.js)
│   ├── src/routes/    # Auth, channels, jobs, content, workspace, user, notifications
│   ├── src/middleware/# JWT auth, rate limiting
│   ├── src/cron/      # Workspace deletion cron
│   └── src/repositories/# Database access layer
├── streaming-hub/     # SSE/WebSocket hub (Node.js)
│   ├── src/routes/    # SSE, WebSocket, publish endpoints
│   └── src/hub.ts     # Redis pub/sub event fan-out
└── core/              # FastAPI microservices (Python)
    ├── research/      # Research & topic generation
    ├── script/        # Script generation
    ├── voice/         # TTS synthesis
    ├── assets/        # Stock media search
    ├── thumbnail/     # Thumbnail generation
    ├── assembly/      # Video assembly
    ├── delivery/      # YouTube upload
    ├── analytics/     # Analytics & retention
    ├── admin/         # Admin operations
    ├── direction/     # Direction generation
    ├── brand/         # Brand voice
    ├── brain/         # Adaptive decision engine
    ├── editor/        # Editor operations
    ├── sheets_sync/   # Google Sheets sync
    └── dashboard/     # Dashboard BFF
```

### 2. AI Services (`backend/ai/`)

Machine learning and AI inference.

```
backend/ai/
└── model-server/      # ML model inference (Python)
    ├── models/        # Model definitions
    └── inference/     # Inference endpoints
```

### 3. Workers (`backend/workers/`)

Background processing and async workflows.

```
backend/workers/
├── temporal/          # Temporal workflows + activities (Python)
│   ├── workers/
│   │   ├── workflows/ # 8 workflows (video production, scheduler, etc.)
│   │   ├── activities/# 15 activity modules
│   │   ├── run_production.py  # Production worker
│   │   ├── run_scheduler.py   # Scheduler worker
│   │   └── media_jobs/        # Media job handlers
│   └── README.md
└── notification-dispatcher/   # Notification dispatcher (Python)
    ├── src/channels.py        # Slack, email, webhook
    └── src/dispatcher.py      # Polling + retry logic
```

### 4. Media (`backend/media/`)

Media processing and rendering.

```
backend/media/
└── remotion/          # Video rendering (Node.js + Remotion)
    ├── src/
    │   ├── api/       # REST API for render jobs
    │   ├── worker/    # Worker pool (tier1, tier2)
    │   ├── compositions/# Remotion compositions
    │   ├── scene-graph/# Scene graph compiler
    │   └── templates/ # Video templates
    └── Dockerfile
```

### 5. Platform (`backend/platform/`)

Platform services (monitoring, cleanup, etc.).

```
backend/platform/
├── resolve-finisher/  # DaVinci Resolve integration (Python)
│   └── app.py
└── sentry-agent/      # Sentry error triage + auto-fix (Python)
    ├── bot.py         # Slack bot
    ├── triage.py      # Error triage
    └── fix_agent.py   # LLM-powered auto-fix
```

## Shared (`shared/`)

Reusable code shared across frontend and backend.

### Python (`shared/python/`)

```
shared/python/
├── contracts/         # Pydantic models (generated from Zod)
├── core/              # Config, DB, environment, flags, Redis
├── events/            # Event bus (Redis pub/sub)
├── intelligence/      # Niche templates, diversity floor, uniqueness guard
├── llm/               # LLM router, compressor, embeddings
├── observability/     # Metrics, Sentry, budget tracking
├── providers/         # Provider registry + implementations
│   ├── llm/           # OpenAI, Claude, Gemini, DeepSeek, etc.
│   ├── image/         # DALL-E, Flux, Stability
│   ├── tts/           # ElevenLabs, Cartesia, Edge TTS, Fish Audio
│   ├── search/        # SerpAPI
│   ├── stock/         # Pexels, Unsplash, Pixabay, Kling
│   └── storage/       # MinIO
├── quality/           # Quality gates, calibration, retention features
├── schemas/           # Common schemas
└── agents/            # Agentic components (base, critic, reasoner, memory, preventor)
```

### TypeScript (`shared/ts/`)

```
shared/ts/
└── contracts/         # Zod schemas (source of truth)
    ├── src/
    │   ├── auth.schema.ts
    │   ├── common.schema.ts
    │   ├── job.schema.ts
    │   └── generate-openapi.ts
    └── openapi.json   # Generated OpenAPI spec
```

## Infrastructure (`infra/`)

Infrastructure configuration and deployment.

```
infra/
├── traefik/           # Traefik reverse proxy configs
│   ├── traefik.yml    # Static config
│   └── dynamic/       # Dynamic routing rules
├── observability/     # Prometheus, Grafana, Loki
│   ├── prometheus.yml
│   ├── alert-rules.yml
│   └── dashboards/
└── config/
    └── dynamicconfig/ # Temporal dynamic config
```

## Scripts (`scripts/`)

Build, deploy, and utility scripts.

```
scripts/
├── init-db.sql        # Database initialization
├── seed-data.sql      # Seed data
├── verify-versions-in-sync.sh  # Version drift check
├── sqlx-prepare.sh    # SQLX cache (legacy, unused)
└── ci-local.sh        # Local CI simulation
```

## Tools (`tools/`)

Development tools and code generators.

```
tools/
├── gen-pydantic.sh    # Generate Pydantic from OpenAPI
└── (other generators)
```

## Docs (`docs/`)

Architecture documentation and ADRs.

```
docs/
├── architecture/
│   ├── adr-004-two-language-simplification.md  # Current stack decision
│   ├── agentic-framework.md
│   ├── dashboard-section-inventory.md
│   ├── design-system.md
│   ├── infrastructure.md
│   ├── mass-content-safety.md
│   ├── opsrule-engine-and-config.md
│   ├── provider-interfaces.md
│   ├── quality-gates.md
│   ├── remotion-integration.md
│   ├── script-architecture.md
│   ├── security.md
│   ├── service-contracts.md
│   └── toolchain.md
└── workflows/         # Workflow documentation
```

## Root Files

```
.
├── docker-compose.yml         # Local dev stack
├── docker-compose.test.yml    # Test stack
├── Dockerfile                 # Python services image
├── pyproject.toml             # Python monorepo config (uv)
├── package.json               # Root package.json (pnpm workspace)
├── pnpm-workspace.yaml        # pnpm workspace config
├── tsconfig.base.json         # Base TypeScript config
├── ruff.toml                  # Python linter config
├── .tool-versions             # asdf/mise version pins
├── versions.env               # Version pins for CI
├── .husky/                    # Git hooks
├── .github/workflows/         # GitHub Actions CI
├── CHANGELOG.md               # Migration history
├── STRUCTURE.md               # This file
└── README.md                  # Project README
```

## Key Principles

1. **Clear separation of concerns:** Frontend, backend (5 categories), shared, infra.
2. **Two-language stack:** Python (backend, ML, workflows) + TypeScript (frontend, gateway, streaming).
3. **Contracts-first:** Zod schemas → OpenAPI → Pydantic for type-safe APIs.
4. **Monorepo:** All code in one repo, managed by uv (Python) and pnpm (TypeScript).
5. **Docker Compose:** Local dev stack with all services.
6. **Temporal:** Workflow orchestration for video production and scheduled tasks.
7. **Traefik:** Reverse proxy with TLS termination and header-based routing.

## Migration Notes

This structure is the result of the Phase 7 cleanup (August 2026):
- Deleted all Rust/Go code and protobuf definitions.
- Renamed `libs/` → `shared/`.
- Renamed `apps/` → `frontend/`.
- Renamed `services/` → `backend/` with 5-way split (api, ai, workers, media, platform).
- Removed `-v2` suffixes from all services and Temporal queues.
- Consolidated migration docs into `CHANGELOG.md`.

See `CHANGELOG.md` for full migration history.
