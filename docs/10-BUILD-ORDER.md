# Build Order & Timeline

> 12-week phased build plan. First video by Week 6. 10-channel steady state by Week 12.

---

## Phase Overview

| Phase | Weeks | Goal |
|-------|-------|------|
| **1: Foundation** | 1-2 | Docker stack, Temporal, DB schema, provider interfaces, first service |
| **2: Core Pipeline** | 3-5 | Research → Script → Voice → Assets → Assembly services |
| **3: First Video** | 6 | End-to-end: one video from research to rendered MP4 |
| **4: Delivery & QA** | 7-8 | YouTube upload, human review, quality gates |
| **5: Intelligence** | 9-10 | Analytics, trends, performance memory, budget guards |
| **6: Hardening** | 11-12 | Monitoring, backups, security, multi-channel testing |

---

## Week 1: Infrastructure Bootstrap

**Deliverables:**
- Docker Compose running: Temporal server, PostgreSQL (×2), Redis, MinIO, Traefik
- Temporal Web UI accessible
- PostgreSQL schema created (`scripts/init-db.sql`)
- MinIO buckets created
- `.env` configured with all provider keys
- Provider interface abstract base classes created

**Verification:**
```bash
docker compose up -d
# Temporal UI at localhost:8080
# MinIO console at localhost:9001
# psql -h localhost -U app -d autonix  (schema exists)
```

---

## Week 2: First Service + Worker

**Deliverables:**
- `services/research/` — FastAPI service with `/research` endpoint
- `workers/production.py` — Temporal worker connecting to server
- `DailySchedulerWorkflow` (minimal: just logs)
- `VideoProductionWorkflow` (minimal: just research_activity)
- Provider interfaces: `LLMProvider`, `SearchProvider` implemented for OpenAI + SerpAPI
- Shared library: `lib/providers/`, `lib/schemas/`, `lib/config/`

**Verification:**
```bash
# Start research service
curl http://localhost:5001/health  # → 200

# Start Temporal worker, trigger workflow via Temporal UI
# Research activity runs → returns research_package
```

---

## Week 3: Script + Voice Services

**Deliverables:**
- `services/script/` — Script generation, critique, rewrite, hooks, metadata
- `services/voice/` — TTS via Fish Audio PAYG, per-scene audio
- `TTSProvider` interface + `FishAudioTTS` implementation
- View A transform: `script_base → script_voice.json`
- View B transform: `script_base → script_assets.json`
- VideoProductionWorkflow updated: research → script → voice (sequential)
- Idempotency key generation for all activities

**Verification:**
```bash
# Trigger workflow
# Research → Script → Voice runs end-to-end
# Audio files appear in MinIO: s3://autonix/audio/...
# script_base.json + script_voice.json in MinIO
```

---

## Week 4: Assets + Thumbnail Services

**Deliverables:**
- `services/assets/` — Stock footage search (Pixabay/Pexels), music, SFX
- `services/thumbnail/` — Concept generation + DALL-E rendering + QC
- `ImageProvider` interface + `DALLEProvider` implementation
- Redis caching for assets (30-day TTL)
- Parallel execution: voice + assets + thumbnail in workflow

**Verification:**
```bash
# Trigger workflow
# Voice, Assets, Thumbnail run in parallel
# Asset manifest in MinIO
# Thumbnail PNGs in MinIO
# Temporal UI shows parallel activities
```

---

## Week 5: Assembly Service + v3 JSON

**Deliverables:**
- `services/assembly/` — Direction Engine, v3 JSON generation, quality gates
- View C transform: `all inputs → script_remotion.json`
- Quality gates implemented (all 30+)
- Content fingerprinting + cross-channel dedup
- Full pipeline: research → script → parallel(voice, assets, thumbnail) → assembly

**Verification:**
```bash
# Trigger workflow
# Assembly produces v3 JSON in MinIO
# Quality report generated
# Content fingerprint stored in Redis + PostgreSQL
# All 30+ quality gates evaluated
```

---

## Week 6: First Video (Milestone)

**Deliverables:**
- Remotion integration: `render_activity` calling Remotion API
- End-to-end pipeline produces a real MP4 video
- Remotion repo connected (same Docker network or VPN)
- Video stored in MinIO

**Verification:**
```bash
# Trigger workflow for one channel
# Complete pipeline runs: research → script → assets → assembly → render
# Video.mp4 in MinIO
# Watch it! Quality check manually
```

**This is the critical milestone.** Everything after this is polish, delivery, and hardening.

---

## Week 7: Delivery Service + YouTube Upload

**Deliverables:**
- `services/delivery/` — YouTube upload via YouTube Data API v3
- OAuth2 token management for YouTube
- Metadata injection (title, description, tags, AI disclosure)
- Niche-specific disclaimers auto-injected
- Upload scheduling (stagger across channels)

**Verification:**
```bash
# Trigger full pipeline
# Video uploads to YouTube (as unlisted first)
# Metadata correct
# AI disclosure present
```

---

## Week 8: Human Review + Admin API

**Deliverables:**
- `services/admin/` — REST API with JWT auth
- Human review signal flow: notification → approve/reject → workflow resumes
- Admin API: channel CRUD, system controls, emergency stop
- Temporal query for workflow status

**Verification:**
```bash
# Trigger workflow → score < 8.0 → human review notification sent
# Approve via Admin API → workflow resumes → video delivered
# Reject → workflow terminates
# Emergency stop → all workflows paused
```

---

## Week 9: Analytics + Trends

**Deliverables:**
- `services/analytics/` — YouTube Analytics API integration
- `AnalyticsWorkflow` — weekly, updates performance memory
- `TrendScanWorkflow` — every 8h, caches trend data
- Performance memory feeds into research/script activities

**Verification:**
```bash
# After 1 week of uploads: analytics workflow collects data
# Performance patterns stored in PostgreSQL
# Trend data cached in Redis
# Next research activity uses trends + patterns
```

---

## Week 10: Budget Guards + Cost Tracking

**Deliverables:**
- Budget guard in every activity (pre-flight cost check)
- Daily budget cap enforcement in scheduler
- `api_usage` table tracking all costs
- Cost alerts (80% threshold, per-video spike)
- Admin API: `/costs` endpoint

**Verification:**
```bash
# Set daily_budget_limit = $5
# Trigger enough workflows to approach limit
# Scheduler stops triggering when budget exhausted
# Cost report shows per-video and per-provider breakdown
```

---

## Week 11: Monitoring + Backups

**Deliverables:**
- Structured JSON logging in all services
- PostgreSQL backup script (daily cron)
- MinIO versioning enabled
- Basic alerting (service down, high error rate, disk space)
- Temporal Web UI: review workflow health

**Verification:**
```bash
# Backup runs at 3 AM → .sql.gz files in MinIO/backups/
# Restore test: drop DB → restore from backup → all data intact
# Kill a service → Docker restarts it → alert fires
```

---

## Week 12: Hardening + Multi-Channel

**Deliverables:**
- Security checklist completed (see `docs/08-SECURITY.md`)
- TLS configured (Traefik + Let's Encrypt)
- SSH hardened (key-only, non-standard port)
- Firewall rules (UFW)
- Circuit breakers tested
- Cross-channel dedup tested with 3 channels
- Load test: simulate 10-channel concurrent production

**Verification:**
```bash
# Run 3 channels simultaneously
# No resource contention
# No cross-channel content duplication
# All videos pass quality gates
# Budget tracking accurate
```

---

## Post-Launch Scaling Roadmap

| Timeframe | Channels | Actions |
|-----------|----------|---------|
| Month 1-2 | 1-3 | Run on single CX31, manual oversight, fix bugs |
| Month 3-4 | 3-5 | Add dedicated render VPS, enable caching aggressively |
| Month 5-6 | 5-10 | Separate DB VPS, add Prometheus + Grafana |
| Month 7-9 | 10-25 | Upgrade main VPS, multiple render VPSes, reduce manual review |
| Month 10-12 | 25-50 | CX51 for services, 3 render VPSes, automated everything |
| Year 2 | 50-100+ | Consider Kubernetes, read replicas, CDN for assets |

---

## Testing Strategy

| Level | Tool | When |
|-------|------|------|
| Unit tests | pytest | Every service, every PR |
| Integration tests | pytest + httpx | Service-to-service contracts |
| Workflow tests | Temporal test framework | Workflow logic (mocked activities) |
| End-to-end | Manual trigger + verify | Weekly during build, daily after launch |
| Load test | locust or k6 | Before scaling milestones |

### Temporal Workflow Testing

```python
from temporalio.testing import WorkflowEnvironment

async def test_video_production_happy_path():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Register mocked activities
        worker = Worker(
            env.client,
            task_queue="test-queue",
            workflows=[VideoProductionWorkflow],
            activities=[mock_research, mock_script, mock_voice, ...],
        )
        async with worker:
            result = await env.client.execute_workflow(
                VideoProductionWorkflow.run,
                args=[VideoParams(channel_id="TEST01", content_mode="long_form", ...)],
                id="test-run",
                task_queue="test-queue",
            )
            assert result.status == "delivered"
            assert result.cost < 1.0
```
