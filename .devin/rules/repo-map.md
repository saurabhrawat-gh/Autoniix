# Repository Map

```
youtube-automation/
├── .windsurf/              Agent config (rules/, skills/, workflows/)
├── config/                  SQL scripts (init-db.sql, seed-data.sql)
├── dashboard/               Next.js 14 frontend (App Router, TailwindCSS)
│   ├── src/app/             Pages: /login, /dashboard, /channels, /jobs, /settings
│   ├── src/lib/             API client (api.ts), utilities (utils.ts)
│   └── Dockerfile           Multi-stage Node 20 Alpine build
├── docs/                    Architecture docs (00-11 + intelligence + agent framework)
├── public/                  Static assets
├── scripts/                 Utility scripts (init-db.sql, seed-data.sql, generate_training_data.py)
├── services/                Legacy/deprecated — do not add new code here
├── src/                     Application source code
│   ├── config.py            Pydantic Settings (all env vars, database_url property)
│   ├── db.py                Database connection pool
│   ├── environment.py       Test vs Production mode (is_test, get_storage_prefix, etc.)
│   ├── redis_client.py      Redis connection
│   ├── providers/           Provider abstraction layer
│   │   ├── registry.py      ProviderRegistry (config-driven factory)
│   │   ├── boot.py          Auto-imports all providers on startup
│   │   ├── llm/             LLM providers (base, openai, claude, gemini, mock)
│   │   ├── tts/             TTS providers (base, fishaudio, elevenlabs, edge_tts)
│   │   ├── image/           Image providers (base, dalle, placeholder)
│   │   ├── search/          Search providers (base, serpapi, mock)
│   │   └── storage/         Storage providers (base, minio)
│   ├── schemas/             Pydantic schemas (common.py: VideoParams, VideoResult)
│   ├── services/            Business logic microservices
│   │   ├── admin/           Channel/config CRUD
│   │   ├── analytics/       Pattern mining, insights
│   │   ├── assembly/        Direction engine, render config, QC gates
│   │   ├── assets/          Stock search, query optimizer
│   │   ├── brand/           Brand DNA, consistency
│   │   ├── dashboard/       BFF (auth, channels, jobs, WebSocket)
│   │   ├── delivery/        YouTube upload, SEO optimizer
│   │   ├── direction/       Direction merger
│   │   ├── editor/          Timeline, captions, final QC
│   │   ├── experiments/     A/B testing, observability
│   │   ├── research/        Trend collector, competitor insights, similarity, burst detector
│   │   ├── script/          Script intelligence (analyzer, retention, humanizer, prosody, asset, direction, self-learning)
│   │   ├── sheets_sync/     Google Sheets sync
│   │   ├── thumbnail/       CTR predictor, composition analyzer
│   │   └── voice/           Emotion predictor, audio quality, voice style learner
│   ├── temporal_workflows/  Temporal workflow definitions
│   │   ├── video_production.py  Main 13-phase pipeline
│   │   ├── daily_scheduler.py   Cron-based channel scheduling
│   │   ├── model_maintenance.py  Weekly model retrain workflow
│   │   └── model_activities.py   Model health/drift/retrain activities
│   └── workers/             Temporal worker entry points
├── subagents/               Subagent specifications (markdown)
├── tests/                   Test suite (conftest.py, test_*.py)
├── docker-compose.yml       All services (~21 containers)
├── Dockerfile               Python service base image
├── Makefile                 Common commands (up, down, test, lint)
├── pytest.ini               Pytest configuration
└── requirements.txt         Python dependencies
```

## Key Files to Know
- `src/config.py` — All settings. Read this before adding any env var.
- `src/providers/registry.py` — Provider factory. Read this before adding any provider.
- `src/environment.py` — Test vs Production mode. Read this before any feature that behaves differently per environment.
- `src/temporal_workflows/video_production.py` — The main pipeline. 721 lines. 13 phases.
- `scripts/init-db.sql` — All DB tables. Read this before adding any table.
- `scripts/seed-data.sql` — All seed data + system_config keys. Read this before adding config.
