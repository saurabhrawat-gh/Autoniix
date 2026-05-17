# Architecture Overview

## Purpose

Autoniix is a self-hosted, AI-driven content factory that produces YouTube
videos end-to-end — from topic research to upload — with human-in-the-loop
review available via workflow signals. The system is designed for **day-1
scalability** (1 to 100+ channels), **provider-swappable** components, and
**fault-tolerant** durable workflows.

## Source files

- `docker-compose.yml` — full container topology (~25 services)
- `src/temporal_workflows/video_production.py:1-200` — main workflow
- `src/providers/registry.py:1-171` — provider registry
- `src/config.py:1-127` — Pydantic settings
- `docs/00-OVERVIEW.md`, `docs/01-ARCHITECTURE.md` — long-form internal docs

## High-level diagram

```
                       ┌──────────────────┐
                       │  Traefik gateway   │  TLS · routing · admin-auth
                       └─┬────────┬──────┘
                         │        │
           ┌─────────────┘        └─────────────┐
  ┌────────▼───────┐                  ┌──────────▼────────┐
  │  dashboard-ui    │─────HTTP──────│  dashboard-bff   │
  │  Next.js 14      │                  │  FastAPI         │
  └────────────────┘                  └──┬─────────────┘
                                            │ signals + queries
                            ┌────────────────▼───────────────┐
                            │        Temporal Server (+ UI)        │
                            └──┬───────────────────────────────┘
                               │ activity dispatch
             ┌────────────────┼────────────────┐
             │                 │                  │
      ┌─────▼─────┐   ┌───────▼──────┐   ┌──────▼─────┐
      │ worker-     │   │  worker-      │   │ remotion-    │
      │ production  │   │  scheduler    │   │ worker(s)    │
      └─────┬─────┘   └───────┬──────┘   └──────┬─────┘
            │                 │                  │
            └─── calls FastAPI services on the autoniix-net bridge ──────┘
```

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestrator | Temporal (self-hosted) | Durable, retries, versioning |
| Service language | Python 3.12 + FastAPI | Best AI/ML ecosystem |
| Render engine | Remotion (TS, separate repo) | Code-driven, 48+ components |
| Primary DB | PostgreSQL 15 + pgvector | ACID, vector search |
| Cache | Redis 7 | Sub-ms latency, pub/sub |
| Object storage | MinIO (S3-compatible) | Self-hosted, free, versioning |
| Gateway | Traefik 3.1 | Docker-native, ACME |
| Monitoring | Prometheus + Grafana + Loki | Industry standard |

## End-to-end data flow (one video)

1. **Trigger** — dashboard or `DailySchedulerWorkflow` starts `VideoProductionWorkflow` with `VideoParams`.
2. **Research** — trends + competitors + opportunity scoring → topic + angle.
3. **Brand check** — brand DNA consistency.
4. **Script** — 13-step generation (LLM + local intelligence).
5. **Voice** — TTS with prosody/emotion knobs.
6. **Assets** — Pexels/Pixabay/local library + DALL·E fallback.
7. **Thumbnail** — DALL·E + GPT-4o Vision QC + regeneration loop.
8. **Direction** — per-segment camera/text/motion/SFX.
9. **Post-production (editor)** — timeline, captions, final QC.
10. **Render** — Remotion API enqueues BullMQ job; worker renders to MinIO.
11. **Delivery** — YouTube upload via OAuth (production mode only).
12. **Analytics** — fetch metrics, feed into self-learning.

Each phase calls `update_video_status` + `emit_job_event`, so the dashboard
Progress page stays live via WebSocket polling.

## Operating modes

- **test** (default) — mock providers, free Edge TTS, $0/video, 640×360@15fps, no upload.
- **production** — real LLMs, real TTS, full HD render, real upload, budget gated.

See [[Test-vs-Production-Mode]].

## Related pages

- [[Architecture-Data-Layer]]
- [[Architecture-Container-Topology]]
- [[Architecture-Provider-Pattern]]
- [[Workflow-VideoProduction]]
