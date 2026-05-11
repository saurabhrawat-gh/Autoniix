# YouTube Automation Platform — Master Architecture

> **Version:** 2.0 | **Updated:** April 25, 2026
> **Architecture:** Self-hosted Temporal Microservices
> **Language:** Python (FastAPI) | TypeScript (Remotion only)
> **Status:** Architecture Finalized — Ready to Build

---

## Vision

A fully automated, premium-quality YouTube content production platform. Every video — from research to upload — is produced without manual intervention, with human-in-the-loop review available via workflow signals. The system is designed for **day-1 scalability** (1 to 100+ channels), **provider-swappable** components, and **fault-tolerant** durable workflows.

---

## Locked Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Orchestrator** | Temporal (self-hosted, OSS) | Durable workflows, built-in retries, versioning, $0 license |
| **Services language** | Python 3.12 + FastAPI | Best AI/ML ecosystem, async, type-safe |
| **Render engine** | Remotion (TypeScript, separate repo) | Code-driven video, 48+ components, BullMQ queue |
| **TTS provider** | Fish Audio (PAYG, $0.0208/min) | 77-89% cheaper than ElevenLabs; swappable |
| **LLM stack** | GPT-4o, Claude Sonnet, Gemini Flash, GPT-4o-mini | Each model assigned by task strength |
| **Primary database** | PostgreSQL 15 | ACID, partitioning, JSON support, no rate limits |
| **Cache** | Redis 7 | Sub-ms latency, pub/sub, rate limiting |
| **Object storage** | MinIO (S3-compatible) | Self-hosted, free, versioning |
| **API gateway** | Traefik | Docker-native, auto-discovery, TLS, free |
| **Monitoring** | Temporal Web UI + Prometheus + Grafana | Industry standard |
| **Infrastructure** | Hetzner Cloud VPS | Best price/performance in EU |
| **Container orchestration** | Docker Compose → Kubernetes (at scale) | Start simple, scale later |
| **Provider pattern** | Abstract base classes + config registry | Swap any provider via env var + one file |

---

## Architecture Diagram

```
                          ┌─────────────────────────┐
                          │    Traefik (Gateway)     │
                          │  TLS · Auth · Routing    │
                          └────────────┬────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
    ┌─────────▼────────┐    ┌─────────▼────────┐    ┌─────────▼────────┐
    │  TEMPORAL SERVER  │    │   ADMIN API      │    │   MONITORING     │
    │  + Web UI         │    │   (FastAPI)      │    │   Prometheus     │
    │  + Admin Tools    │    │   JWT · RBAC     │    │   + Grafana      │
    └────────┬─────────┘    └──────────────────┘    └──────────────────┘
             │
             │  Activities (service calls)
             │
    ┌────────┴──────┬────────────┬────────────┬────────────┬────────────┐
    │               │            │            │            │            │
┌───▼────┐   ┌─────▼───┐  ┌─────▼───┐  ┌─────▼───┐  ┌────▼────┐  ┌───▼──────┐
│RESEARCH│   │ SCRIPT  │  │  VOICE  │  │ ASSETS  │  │THUMBNAIL│  │ ASSEMBLY │
│SERVICE │   │ SERVICE │  │ SERVICE │  │ SERVICE │  │ SERVICE │  │ SERVICE  │
│        │   │         │  │         │  │         │  │         │  │          │
│FastAPI │   │FastAPI  │  │FastAPI  │  │FastAPI  │  │FastAPI  │  │FastAPI   │
└────────┘   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └──────────┘
    │               │            │            │            │            │
    └───────────────┴────────────┴─────┬──────┴────────────┴────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
   ┌─────▼──────┐              ┌───────▼───────┐             ┌──────▼──────┐
   │  RENDER    │              │  DELIVERY     │             │  ANALYTICS  │
   │  SERVICE   │              │  SERVICE      │             │  SERVICE    │
   │ (Remotion) │              │  Upload +     │             │  YouTube    │
   │ Separate   │              │  Notify       │             │  API +      │
   │ Repo + VPS │              │               │             │  Patterns   │
   └────────────┘              └───────────────┘             └─────────────┘
         │                             │                             │
    ┌────┴─────────────────────────────┼─────────────────────────────┘
    │                                  │
┌───▼────────┐    ┌────────────────┐   ┌────────────────┐
│ PostgreSQL │    │ Redis Cache    │   │ MinIO (S3)     │
│            │    │                │   │                │
│ Channels   │    │ API cache      │   │ Scripts        │
│ Videos     │    │ Dedup hashes   │   │ Audio files    │
│ Config     │    │ Rate limits    │   │ Video files    │
│ Analytics  │    │ Trends         │   │ Thumbnails     │
│ Audit logs │    │ Sessions       │   │ Backups        │
└────────────┘    └────────────────┘   └────────────────┘
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Orchestration | Temporal Server (self-hosted) | Latest OSS |
| Services | Python + FastAPI + uvicorn | 3.12 / 0.110+ |
| Task queue | Celery + Redis (per-service, optional) | 5.x |
| Render engine | Remotion + BullMQ (TypeScript) | 4.x |
| Database | PostgreSQL | 15 |
| Cache | Redis | 7-alpine |
| Object storage | MinIO | Latest |
| API gateway | Traefik | 3.x |
| Monitoring | Prometheus + Grafana | Latest |
| Secrets | Docker secrets → HashiCorp Vault (roadmap) | — |
| Containers | Docker Compose → Kubernetes (at scale) | — |
| CI/CD | GitHub Actions | — |

---

## Content Strategy

| Parameter | Value |
|-----------|-------|
| Long-form duration | 8 min (~1100 words) |
| Short-form duration | 45 sec (~80 words) |
| Month 1-2 cadence | 1 long + 7 shorts / week / channel |
| Month 3+ cadence | 2 longs + 3 shorts / week / channel |
| Visual-only scenes | 12% of long-form |
| Quality threshold | ≥ 8.0 composite score |
| Voice | 100% narrated, unique voice per channel |

---

## Account Structure

| Account | Email | Purpose |
|---------|-------|---------|
| Management | yt.empire.management@gmail.com | Brand Accounts (up to 100 channels) |
| AdSense | saurabhrawat.official@gmail.com | Revenue (ONE account, ALL channels) |
| Additional management | New Gmail per 100 channels | Same AdSense linked |

---

## Channels (Initial)

| Brand | Niche | Channels |
|-------|-------|----------|
| Body Signals | Health | 5 |
| Money Decoded | Finance | 3 |
| Mind Shifts | Psychology | 2 |

---

## LLM Assignment (Hybrid Model Stack)

| Task | Model | Why |
|------|-------|-----|
| Research synthesis | Gemini 2.5 Flash | Cost-optimized, structured JSON |
| Script writing | Claude Sonnet | Superior creative writing |
| Script critique | GPT-4o-mini | Cost-optimized, simpler task |
| Fact-checking | GPT-4o (temp 0.1) | Most reliable |
| Scene Descriptor v3 | GPT-4o | Best complex JSON output |
| Direction Engine | GPT-4o | Creative-to-technical translation |
| All QC/Scoring | Gemini 2.5 Flash | 94% cheaper, fast |
| Tags, desc, emotion | GPT-4o-mini | Simple tasks, cheap |
| Audience simulation | Claude Sonnet | Best role-playing |
| Thumbnail QC | GPT-4o Vision | Can "see" the thumbnail |

All models are swappable via `LLMProvider` interface (see `docs/11-PROVIDER-INTERFACES.md`).

---

## Credentials & Secrets

**No credentials are stored in documentation.**

All secrets are managed via:
1. **Development:** `.env` file (git-ignored)
2. **Production:** Docker secrets or HashiCorp Vault

Required secret keys (configure in `.env`):
```
# Database
DB_PASSWORD=
REDIS_URL=redis://redis:6379

# AI Providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_AI_API_KEY=

# TTS
FISH_AUDIO_API_KEY=

# Search
SERPAPI_KEY=

# Image
PIXABAY_API_KEY=

# YouTube
YOUTUBE_API_KEY=

# Storage (MinIO / S3)
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=
S3_PUBLIC_BASE_URL=

# Google OAuth (for YouTube uploads)
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REFRESH_TOKEN=

# Admin
ADMIN_JWT_SECRET=
```

---

## Documentation Index

| Doc | Contents |
|-----|----------|
| **00-OVERVIEW.md** | This file — master overview, decisions, stack |
| **01-ARCHITECTURE.md** | Full system architecture, data layer, network, security model |
| **02-SERVICE-CONTRACTS.md** | API contracts, payload schemas, Temporal activity specs |
| **03-SCRIPT-ARCHITECTURE.md** | Script engine: 3 views (voiceover, assets, Remotion v3) |
| **04-TEMPORAL-WORKFLOWS.md** | Workflow definitions, signals, budget guards, versioning |
| **05-QUALITY-GATES.md** | 30+ quality gates, anti-inflation, human review |
| **06-REMOTION-INTEGRATION.md** | Render engine integration contract (separate repo) |
| **07-COST-ANALYSIS.md** | Complete cost breakdown: 1/3/5/10/25/50/100 channels |
| **08-SECURITY.md** | Secrets, JWT, RBAC, TLS, YouTube policy, audit |
| **09-INFRASTRUCTURE.md** | Docker Compose, sizing, backups, monitoring, K8s roadmap |
| **10-BUILD-ORDER.md** | 10-12 week phased build timeline |
| **11-PROVIDER-INTERFACES.md** | Abstract base classes, config registry, fallback chains |

### Related Repositories

| Repo | Path | Purpose |
|------|------|---------|
| autonix | This repo | Temporal orchestrator + Python services |
| yt-automation-remotion | `../yt-automation-remotion` | Remotion render engine (TypeScript) |

### Archived Documentation

Previous architecture docs (monolith, hybrid, microservices exploration) are preserved in `docs/archive/`.
