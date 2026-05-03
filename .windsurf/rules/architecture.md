# Architecture Rules

## System Overview
YouTube content automation: Temporal microservices + Python FastAPI + PostgreSQL + Redis + MinIO + Remotion (TypeScript). Self-hosted, local-first intelligence, LLM-fallback.

## Service Ownership (strict boundaries)

| Service | Port | Owns |
|---------|------|------|
| Research | 5001 | Topic research, competitor analysis, trend signals, burst detection, opportunity scoring |
| Script | 5002 | Script writing, critique, rewrite, hooks, metadata, script intelligence (NLP, retention, humanizer) |
| Voice | 5003 | TTS synthesis, emotion prediction, audio quality scoring, voice style learning |
| Assets | 5004 | Stock footage/music/SFX search, query optimization, scoring, dedup |
| Thumbnail | 5005 | Concept generation, DALL-E rendering, CTR prediction, composition analysis, QC |
| Assembly | 5006 | Direction engine, v3 JSON, render config, 30+ quality gates, compliance checks |
| Direction | 5006* | Direction merger, camera/text/motion/audio/background per segment |
| Delivery | 5007 | YouTube upload, metadata injection, AI disclosure, SEO optimization |
| Analytics | 5008 | YouTube API analytics, pattern mining, insights |
| Admin | 5009 | REST API for channels, config, controls, audit |
| Brand | 8012 | Brand DNA, consistency checks |
| Editor | 8013 | Timeline optimization, caption generation, final QC |
| Dashboard BFF | 8020 | Auth, channel CRUD, job progress, WebSocket, config |
| Dashboard UI | 3000 | Next.js 14 frontend |

*Direction runs as a module inside Assembly service, not a separate container.

## Data Flow
```
Research → Script → Voice → Assets → Thumbnail → Assembly → Render (Remotion) → Delivery → Analytics
                ↘ Direction ↗              ↗
```

## Hard Constraints
- Services communicate via HTTP only (Docker network). No shared DB access across services.
- Workers call services; services never call workers.
- Temporal owns orchestration. Services own business logic.
- Provider pattern (ABC + Registry) for all external APIs: LLM, TTS, Image, Search, Storage.
- Intelligence modules are local-first (spaCy, textstat, NLTK, sklearn, numpy). Zero additional API cost.
- Budget guard on every LLM call. `accrued + estimated > max` → abort.

## Temporal Workers
| Worker | Task Queue | Activities |
|--------|------------|------------|
| production-worker | video-production | research, script, voice, assets, thumbnail, assembly |
| render-worker | video-render | render (Remotion API), delivery |
| analytics-worker | analytics | analytics, trend scan |
| scheduler-worker | scheduler | channel eligibility, schedule checks |
