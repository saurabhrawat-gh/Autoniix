# Architecture Option 3: Full Microservices (Temporal)

> No n8n | Fish Audio TTS | PostgreSQL + Redis + S3 | Temporal orchestrator
> Build time: 10-12 weeks | Best for: 50-1000+ channels (long-term platform)

---

## Overview

Complete microservices architecture. **n8n is fully replaced** by Temporal (durable workflow engine). Every engine is an independent service with its own error handling, scaling, and lifecycle.

**Key decisions:**
- **Orchestration:** Temporal (replaces n8n) — durable workflows, built-in retries, versioning
- **Voice:** Fish Audio API (replaces ElevenLabs) — 77-89% cheaper
- **Database:** PostgreSQL (primary) + Redis (cache) + MinIO (object storage)
- **Services:** 10 independent Python/Node.js microservices
- **Deployment:** Docker Compose (small scale) → Kubernetes (large scale)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Gateway (Traefik)                        │
│              Authentication, Rate Limiting, Routing              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌───────▼────────┐   ┌───────▼────────┐
│  TEMPORAL       │   │  ADMIN API     │   │  MONITORING    │
│  ORCHESTRATOR   │   │  (FastAPI)     │   │  (Prometheus   │
│                 │   │                │   │   + Grafana)   │
│ - Schedules     │   │ - Auth (JWT)   │   │                │
│ - Workflows     │   │ - Channel CRUD │   │ - Metrics      │
│ - Retries       │   │ - Controls     │   │ - Alerts       │
│ - Checkpoints   │   │ - Audit logs   │   │ - Dashboards   │
│ - Versioning    │   │ - Budget mgmt  │   │                │
└────────┬────────┘   └────────────────┘   └────────────────┘
         │
         │ Activities (function calls to services)
         │
    ┌────┴────┬──────────┬──────────┬──────────┬──────────┐
    │         │          │          │          │          │
┌───▼───┐ ┌──▼────┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────┐
│RESEARCH│ │SCRIPT │ │VOICE  │ │ASSETS │ │THUMB  │ │ASSEMBLY│
│SERVICE │ │SERVICE│ │SERVICE│ │SERVICE│ │SERVICE│ │SERVICE │
│        │ │       │ │       │ │       │ │       │ │        │
│FastAPI │ │FastAPI│ │FastAPI│ │FastAPI│ │FastAPI│ │FastAPI │
│+Celery │ │+Celery│ │       │ │+Celery│ │       │ │+Celery │
└───┬────┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬────┘
    │          │         │         │         │         │
    └──────────┴─────────┴────┬────┴─────────┴─────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌────▼─────┐     ┌───────▼──────┐     ┌──────▼──────┐
    │ RENDER   │     │ DELIVERY     │     │ ANALYTICS   │
    │ SERVICE  │     │ SERVICE      │     │ SERVICE     │
    │          │     │              │     │             │
    │ Remotion │     │ Upload +     │     │ YouTube API │
    │ + Queue  │     │ Notifications│     │ + Patterns  │
    └──────────┘     └──────────────┘     └─────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
┌───▼────────┐      ┌────────▼────────┐      ┌────────▼────────┐
│ PostgreSQL │      │ Redis Cache     │      │ MinIO (S3)      │
│            │      │                 │      │                 │
│ - Channels │      │ - API responses │      │ - Scripts       │
│ - Videos   │      │ - Dedup hashes  │      │ - Audio files   │
│ - Beliefs  │      │ - Trend data    │      │ - Video files   │
│ - Config   │      │ - Rate limits   │      │ - Thumbnails    │
│ - Analytics│      │ - Sessions      │      │ - Backups       │
└────────────┘      └─────────────────┘      └─────────────────┘
```

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Orchestration** | Temporal (self-hosted) | Durable workflows, versioning, built-in retries |
| **Services** | Python FastAPI | Async, type-safe, great for AI/ML workloads |
| **Workers** | Celery + Redis | Proven task queue for heavy processing |
| **Database** | PostgreSQL 15 | ACID, partitioning, JSON support |
| **Cache** | Redis 7 | Sub-ms latency, pub/sub, rate limiting |
| **Object Storage** | MinIO | S3-compatible, self-hosted, free |
| **API Gateway** | Traefik | Auto-discovery, Docker-native, free |
| **Monitoring** | Prometheus + Grafana | Industry standard, rich ecosystem |
| **Secrets** | Docker Secrets / Vault (later) | Secure credential management |
| **Container** | Docker Compose → Kubernetes | Start simple, scale later |

---

## Temporal Workflow Definition

### Main Video Production Workflow

```python
from temporalio import workflow, activity
from datetime import timedelta

@workflow.defn
class VideoProductionWorkflow:
    """Produces one video from research to delivery."""

    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:

        # Step 1: Research (with retry, 5 min timeout)
        research = await workflow.execute_activity(
            research_activity,
            args=[params.channel_id, params.content_mode, params.topic_candidates],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                backoff_coefficient=2.0
            )
        )

        # Checkpoint: research complete
        workflow.logger.info(f"Research complete for {params.channel_id}")

        # Step 2: Script generation (10 min timeout)
        script = await workflow.execute_activity(
            script_activity,
            args=[research, params.channel_id],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Checkpoint: script complete
        workflow.logger.info(f"Script complete, score: {script.quality_score}")

        # Step 3: Parallel asset generation (voice + stock + thumbnail)
        voice_task = workflow.execute_activity(
            voice_activity,
            args=[script, params.channel_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        assets_task = workflow.execute_activity(
            assets_activity,
            args=[script],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        thumbnail_task = workflow.execute_activity(
            thumbnail_activity,
            args=[script, params.channel_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Wait for all three in parallel
        voice, assets, thumbnail = await asyncio.gather(
            voice_task, assets_task, thumbnail_task
        )

        # Checkpoint: all assets ready
        workflow.logger.info("All assets generated")

        # Step 4: Assembly + QA (8 min timeout)
        assembly = await workflow.execute_activity(
            assembly_activity,
            args=[script, voice, assets, thumbnail, params.channel_id],
            start_to_close_timeout=timedelta(minutes=8),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Quality gate
        if assembly.final_score < 8.0:
            # Flag for human review
            await workflow.execute_activity(
                notify_human_review,
                args=[assembly, params.channel_id]
            )
            # Wait for human signal (up to 48 hours)
            approved = await workflow.wait_condition(
                lambda: self.human_approved,
                timeout=timedelta(hours=48)
            )
            if not approved:
                return VideoResult(status="rejected", reason="human_review_timeout")

        # Step 5: Render (20 min timeout with heartbeat)
        render = await workflow.execute_activity(
            render_activity,
            args=[assembly.v3_json, params.channel_id],
            start_to_close_timeout=timedelta(minutes=20),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Step 6: Delivery
        result = await workflow.execute_activity(
            delivery_activity,
            args=[render, script.metadata, params.channel_id],
            start_to_close_timeout=timedelta(minutes=5)
        )

        return result

    # Signal handler for human review
    @workflow.signal
    async def approve_video(self, approved: bool):
        self.human_approved = approved
```

### Scheduler Workflow

```python
@workflow.defn
class DailySchedulerWorkflow:
    """Runs every 6 hours, triggers video production for eligible channels."""

    @workflow.run
    async def run(self):
        # Read all active channels
        channels = await workflow.execute_activity(
            get_active_channels_activity,
            start_to_close_timeout=timedelta(seconds=30)
        )

        for channel in channels:
            # Check schedule, locks, budget
            eligible = await workflow.execute_activity(
                check_channel_eligibility_activity,
                args=[channel.id],
                start_to_close_timeout=timedelta(seconds=10)
            )

            if eligible:
                # Start child workflow (runs independently)
                await workflow.start_child_workflow(
                    VideoProductionWorkflow.run,
                    args=[VideoParams(
                        channel_id=channel.id,
                        content_mode=eligible.content_mode,
                        topic_candidates=eligible.topics
                    )],
                    id=f"video-{channel.id}-{date.today()}",
                    task_queue="video-production"
                )
```

---

## Service Specifications

### Service 1: Research Service
- **Tech:** FastAPI + httpx (async HTTP)
- **Code size:** ~400 lines
- **Endpoints:** `POST /research`
- **Calls:** YouTube Data API, SerpAPI, Reddit, Wikipedia, News API
- **LLM:** Gemini Flash (synthesis), GPT-4o (fact verification)
- **Cache:** Redis with 7-day TTL (competitor data, trends)
- **Scaling:** Horizontal, add workers as needed

### Service 2: Script Service
- **Tech:** FastAPI + Celery worker
- **Code size:** ~600 lines
- **Endpoints:** `POST /script`
- **Calls:** Claude Sonnet (script), GPT-4o-mini (critique), OpenAI (hooks, titles)
- **Logic:** Ideation → Script v1 → Critique → Rewrite → Hooks → Metadata
- **Retry:** Built-in max 2 rewrites
- **Scaling:** Horizontal (CPU-bound on LLM waits)

### Service 3: Voice Service
- **Tech:** FastAPI
- **Code size:** ~300 lines
- **Endpoints:** `POST /voice`
- **Calls:** Fish Audio TTS API, GPT-4o-mini (emotion mapping)
- **Logic:** Scene splitting → Emotion mapping → Fish Audio TTS → Timestamp extraction
- **Credit tracking:** Tracks Fish Audio credits per request, enforces budget
- **Scaling:** Horizontal, but Fish Audio API rate limits apply

### Service 4: Assets Service
- **Tech:** FastAPI + Celery worker
- **Code size:** ~400 lines
- **Endpoints:** `POST /assets`
- **Calls:** Pixabay, Pexels, Freesound, Gemini (relevance scoring)
- **Cache:** Redis (asset dedup, 30-day TTL)
- **Logic:** Search → Score → Filter → Dedup → Music/SFX → Manifest
- **Scaling:** Horizontal

### Service 5: Thumbnail Service
- **Tech:** FastAPI
- **Code size:** ~250 lines
- **Endpoints:** `POST /thumbnail`
- **Calls:** GPT-4o (concepts), DALL-E 3 (backgrounds), GPT-4o Vision (QC), Remotion
- **Logic:** Concepts → DALL-E → Remotion render → QC → Selection
- **Scaling:** Limited by DALL-E rate limits

### Service 6: Assembly Service
- **Tech:** FastAPI + Celery worker
- **Code size:** ~500 lines
- **Endpoints:** `POST /assembly`
- **Calls:** GPT-4o (Direction Engine, v3 generation), Gemini (QC gates)
- **Logic:** Direction → v3 JSON → 30 quality gates → Compliance → Packaging
- **Quality gates:** All 30+ gates with configurable thresholds
- **Scaling:** Horizontal

### Service 7: Render Service
- **Tech:** Node.js Express + Bull queue + Remotion
- **Code size:** ~400 lines
- **Endpoints:** `POST /render`, `GET /render/:id`, `GET /health`
- **Logic:** Queue management → Remotion render → Callback
- **Scaling:** Add Remotion workers (separate VPS instances)

### Service 8: Delivery Service
- **Tech:** FastAPI
- **Code size:** ~250 lines
- **Endpoints:** `POST /deliver`
- **Logic:** Package metadata → Inject disclaimers → AI disclosure → Upload prep → Notify
- **Scaling:** Horizontal

### Service 9: Analytics Service
- **Tech:** FastAPI + Celery Beat (scheduler)
- **Code size:** ~400 lines
- **Endpoints:** `POST /analytics`, `POST /trends`, `GET /insights`
- **Cron:** Weekly analytics collection, 3x daily trend scanning
- **Calls:** YouTube Data API, SerpAPI, GPT-4o (pattern analysis)
- **Scaling:** Vertical (cron-based)

### Service 10: Admin Service
- **Tech:** FastAPI + React dashboard (optional)
- **Code size:** ~350 lines (API) + ~1500 lines (React, optional)
- **Endpoints:** Full REST API for channels, config, controls
- **Auth:** JWT with role-based access (admin/operator/viewer)
- **Audit:** All actions logged to database
- **Scaling:** Vertical (low traffic)

---

## Fish Audio Integration

### Plan Selection

| Channels | Plan | Price/month | Credits/month | Usage (Month 3+) | Headroom |
|----------|------|------------|---------------|-------------------|----------|
| 1 | Plus | $11 | 250,000 | ~49,400 | 80% free |
| 3 | Plus | $11 | 250,000 | ~148,200 | 41% free |
| 5 | Plus | $11 | 250,000 | ~247,000 | ~1% free |
| 10 | Pro | $75 | 2,000,000 | ~494,000 | 75% free |

### Voice Service Implementation

```python
# voice_service/main.py
import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI()

FISH_AUDIO_BASE = "https://api.fish.audio/v1"

@app.post("/voice")
async def generate_voice(request: VoiceRequest):
    """Generate voice audio for all scenes in a script."""

    results = []
    total_credits = 0

    for scene in request.scenes:
        # Skip visual-only scenes (no narration)
        if scene.visual_only:
            results.append(SceneAudio(scene_id=scene.id, audio_url=None))
            continue

        # Generate emotion-aware text
        # Fish Audio responds to tone cues in the text itself
        emotion_text = await map_emotion(scene.text, scene.emotion)

        # Call Fish Audio TTS
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FISH_AUDIO_BASE}/tts",
                headers={"Authorization": f"Bearer {FISH_API_KEY}"},
                json={
                    "text": emotion_text,
                    "reference_id": request.voice_id,
                    "format": "mp3",
                    "mp3_bitrate": 128,
                    "normalize": True,
                    "latency": "normal"
                },
                timeout=60.0
            )

            if response.status_code != 200:
                raise HTTPException(500, f"Fish Audio error: {response.text}")

            # Save audio to MinIO
            audio_url = await save_to_storage(
                response.content,
                f"{request.content_id}/scene_{scene.id}.mp3"
            )

            results.append(SceneAudio(
                scene_id=scene.id,
                audio_url=audio_url,
                duration=get_audio_duration(response.content)
            ))

    return VoiceResponse(scenes=results, total_credits=total_credits)
```

---

## Data Layer

### PostgreSQL Schema

```sql
-- Same tables as Hybrid architecture
-- Key difference: more indexes, partitioning for scale

CREATE TABLE channels (
    id VARCHAR(20) PRIMARY KEY,
    channel_name VARCHAR(200) NOT NULL,
    niche VARCHAR(50) NOT NULL,
    sub_niche VARCHAR(100),
    config JSONB NOT NULL,          -- All 63 Channel_DNA columns
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE videos (
    id VARCHAR(50) PRIMARY KEY,     -- e.g., VID_BS001_20250417_001
    channel_id VARCHAR(20) REFERENCES channels(id),
    status VARCHAR(30) NOT NULL,    -- pipeline status
    content_mode VARCHAR(20),
    scores JSONB,                   -- All quality scores
    artifacts JSONB,                -- URLs to scripts, audio, video
    metadata JSONB,                 -- Title, description, tags
    checkpoint VARCHAR(50),         -- Last completed checkpoint
    checkpoint_data_url TEXT,
    total_cost DECIMAL(8,4),
    content_fingerprint TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY HASH (channel_id);

-- Partition for performance at scale
CREATE TABLE videos_p0 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 0);
CREATE TABLE videos_p1 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 1);
-- ... up to videos_p9

CREATE INDEX idx_videos_status ON videos(channel_id, status);
CREATE INDEX idx_videos_fingerprint ON videos(content_fingerprint);
CREATE INDEX idx_videos_created ON videos(created_at DESC);
```

### Redis Usage

```
# Caching layer
research:{channel}:{topic_hash}    → JSON    TTL: 7 days
competitor:{channel_id}            → JSON    TTL: 24 hours
asset:{search_term_hash}          → JSON    TTL: 30 days
trend:{niche}:{date}              → JSON    TTL: 12 hours

# Rate limiting
ratelimit:openai:{minute}         → counter  TTL: 60s
ratelimit:fish_audio:{minute}     → counter  TTL: 60s
ratelimit:serpapi:{day}           → counter  TTL: 24h

# Deduplication
dedup:topic:{hash}                → channel_id  TTL: 90 days
dedup:asset:{hash}                → video_id    TTL: 30 days
dedup:fingerprint:{hash}          → video_id    TTL: 365 days
```

---

## Cost Estimation

### Infrastructure Costs

#### Tier: 1 Channel

| Component | Service | Cost/month |
|-----------|---------|-----------|
| VPS (Temporal + services + DB + Redis + MinIO) | Hetzner CX31 (4 vCPU, 8GB) | $18 |
| VPS (Remotion) | Same VPS or skip initially | $0-7 |
| **Infrastructure subtotal** | | **$18-25** |

> Note: Temporal, PostgreSQL, Redis, MinIO, and all 10 services run as Docker containers
> on a single CX31. This works for 1-3 channels because load is low.

#### Tier: 3 Channels

| Component | Service | Cost/month |
|-----------|---------|-----------|
| VPS (Temporal + services + DB + Redis + MinIO) | Hetzner CX31 | $18 |
| VPS (Remotion) | Hetzner CX21 | $7 |
| **Infrastructure subtotal** | | **$25** |

#### Tier: 5 Channels

| Component | Service | Cost/month |
|-----------|---------|-----------|
| VPS (Temporal + services) | Hetzner CX31 | $18 |
| VPS (DB + Redis + MinIO) | Hetzner CX21 | $7 |
| VPS (Remotion) | Hetzner CX31 | $24 |
| **Infrastructure subtotal** | | **$49** |

#### Tier: 10 Channels

| Component | Service | Cost/month |
|-----------|---------|-----------|
| VPS (Temporal + services) | Hetzner CX41 (8 vCPU, 16GB) | $36 |
| VPS (DB + Redis + MinIO) | Hetzner CX31 | $18 |
| VPS (Remotion) | Hetzner CX31 | $24 |
| Monitoring (Grafana Cloud free tier) | | $0 |
| **Infrastructure subtotal** | | **$78** |

### Per-Video Variable Costs (same as other architectures)

| Component | Long-form ($) | Short-form ($) |
|-----------|:------------:|:-------------:|
| LLM calls (GPT-4o, Claude, Gemini, mini) | 0.65 | 0.17 |
| DALL-E 3 (2 thumbnails) | 0.08 | — |
| SerpAPI (3 queries) | 0.03 | 0.03 |
| Fish Audio (included in plan) | 0.00 | 0.00 |
| **Total per video** | **$0.76** | **$0.20** |

### Monthly Variable Cost per Channel

| Phase | Long-form | Shorts | Total/channel |
|-------|----------|--------|---------------|
| Month 1-2 | $3.29 | $6.06 | **$9.35** |
| Month 3+ | $6.58 | $2.60 | **$9.18** |

---

### Complete Cost: 1 Channel

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Infrastructure (single CX31) | $18 | $18 | Temporal + all services + DB |
| Fish Audio Plus | $11 | $11 | 250K credits |
| LLM variable | $9.35 | $9.18 | |
| SerpAPI | $0 | $0 | Free tier |
| Misc | $2 | $2 | |
| **TOTAL** | **$40** | **$40** | |

### Complete Cost: 3 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Infrastructure (CX31 + CX21) | $25 | $25 | Separate Remotion VPS |
| Fish Audio Plus | $11 | $11 | 250K credits, 41% headroom |
| LLM variable (×3) | $28.05 | $27.54 | |
| SerpAPI | $0 | $0 | Free tier (~195 searches) |
| Misc | $3 | $3 | |
| **TOTAL** | **$67** | **$67** | **$22/channel** |

### Complete Cost: 5 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Infrastructure (CX31 + CX21 + CX31) | $49 | $49 | 3 VPS split |
| Fish Audio Plus | $11 | $11 | At limit month 3+ |
| LLM variable (×5) | $46.75 | $45.90 | |
| SerpAPI Basic | $50 | $50 | |
| Misc | $5 | $5 | |
| **TOTAL** | **$162** | **$161** | **$32/channel** |

### Complete Cost: 10 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Infrastructure (CX41 + CX31 + CX31) | $78 | $78 | 3 VPS, upgraded main |
| Fish Audio Pro | $75 | $75 | 2M credits |
| LLM variable (×10) | $93.50 | $91.80 | |
| SerpAPI Basic | $50 | $50 | |
| Misc | $10 | $10 | |
| **TOTAL** | **$307** | **$305** | **$31/channel** |

---

### Cost Summary Table

| Channels | Monthly Cost | Per Channel | vs Enhanced Monolith | vs Enhanced Hybrid |
|----------|-------------|------------|---------------------|-------------------|
| **1** | **$40** | $40 | Same | Same |
| **3** | **$67** | $22 | +$7 (+12%) | +$7 (+12%) |
| **5** | **$162** | $32 | +$24 (+17%) | +$24 (+17%) |
| **10** | **$307** | $31 | +$18 (+6%) | +$36 (+13%) |

> At small scale (1-5 channels), microservices costs more due to higher infrastructure
> overhead. The payoff comes at 50+ channels where the other architectures hit their ceiling.

### At Scale (where microservices wins)

| Channels | Monolith (ceiling ~15) | Hybrid (ceiling ~50) | Microservices |
|----------|----------------------|---------------------|---------------|
| 25 | ❌ Not possible | ~$400 | ~$460 |
| 50 | ❌ Not possible | ~$750 (near ceiling) | ~$850 |
| 100 | ❌ Not possible | ❌ Not possible | ~$1,600 |
| 500 | ❌ Not possible | ❌ Not possible | ~$7,500 |

### Cumulative Cost (First 12 Months, 1 Channel)

| Month | Monthly | Cumulative | Revenue Est. | Net |
|-------|---------|-----------|-------------|-----|
| 1-2 | $40 | $80 | $0 | -$80 |
| 3-4 | $40 | $160 | $0 | -$160 |
| 5-6 | $40 | $240 | $0-50 | -$190 |
| 7-9 | $40 | $360 | $50-200 | -$160 |
| 10-12 | $40 | $480 | $100-400 | -$80 to +$320 |

---

## Pros & Cons

### Pros
- ✅ **Unlimited scalability** (100-1000+ channels)
- ✅ Complete fault isolation (one service crash doesn't affect others)
- ✅ Durable workflows (survives server crashes, resumes automatically)
- ✅ Workflow versioning (update logic without breaking in-flight videos)
- ✅ True plug-in/plug-out (swap any service independently)
- ✅ Built-in observability (Temporal UI + Prometheus + Grafana)
- ✅ Parallel processing (voice + assets + thumbnail simultaneously)
- ✅ Circuit breakers, dead letter queues, rate limiting — all built-in
- ✅ Professional-grade architecture (used by Netflix, Uber, Stripe)
- ✅ Fish Audio = 77-89% cheaper than ElevenLabs

### Cons
- ❌ **Longest build time** (10-12 weeks)
- ❌ **Steepest learning curve** (Temporal, Docker, distributed systems)
- ❌ More infrastructure to manage (3 VPS at 5+ channels)
- ❌ No visual workflow editor (code-only, no n8n-like UI)
- ❌ **Over-engineered for 1-5 channels** (same cost, more complexity)
- ❌ Temporal cluster itself uses ~1-2GB RAM
- ❌ Need Python/TypeScript expertise (can't use n8n drag-and-drop)
- ❌ Debugging distributed workflows is harder than n8n UI

---

## When This Architecture Makes Sense

### Choose Microservices if:
- ✅ You're planning 50+ channels within the first year
- ✅ You have 10-12 weeks to build before needing production output
- ✅ You have experience with Docker, Python, distributed systems
- ✅ You're building a long-term platform (3+ years)
- ✅ You need enterprise-grade reliability (99.5%+ uptime)

### Do NOT choose Microservices if:
- ❌ You're starting with 1-10 channels (over-engineered)
- ❌ You want to publish your first video within 4-6 weeks
- ❌ You prefer visual workflow editors (n8n)
- ❌ You're solo and don't want infrastructure management overhead
- ❌ Budget is the primary concern for the first year

---

## Build Timeline

| Week | Deliverable |
|------|------------|
| 1-2 | Infrastructure: Docker Compose, PostgreSQL, Redis, MinIO, Temporal |
| 3-4 | Research Service + Script Service (core pipeline) |
| 5-6 | Voice Service (Fish Audio) + Assets Service + Thumbnail Service |
| 7-8 | Assembly Service + Render Service (Remotion) |
| 9-10 | Delivery Service + Analytics Service + Admin API |
| 11-12 | Quality gates, compliance, load testing, first video published |

---

## Migration Path FROM Other Architectures

### From Enhanced Monolith (Doc 10) → Microservices

1. **Week 1-2:** Set up Temporal + PostgreSQL (migrate data from Sheets/PG)
2. **Week 3-4:** Extract B1 → Research Service + Script Service
3. **Week 5-6:** Extract B2 → Voice Service + Assets Service
4. **Week 7-8:** Extract B3/B4 → Thumbnail + Assembly + Render
5. **Week 9-10:** Replace n8n workflows with Temporal workflows
6. **Done:** Decommission n8n

### From Enhanced Hybrid (Doc 09) → Microservices

Easier migration since services already exist:
1. **Week 1-2:** Set up Temporal, point it at existing services
2. **Week 3-4:** Rewrite n8n workflow logic as Temporal workflows
3. **Week 5-6:** Add monitoring, testing, load testing
4. **Done:** Decommission n8n (keep all services as-is)

---

## Final Comparison: All Three Architectures

| Aspect | Monolith (Doc 10) | Hybrid (Doc 09) | Microservices (Doc 11) |
|--------|-------------------|-----------------|----------------------|
| **Build time** | 4 weeks | 5-6 weeks | 10-12 weeks |
| **Min cost (1 ch)** | **$29/mo** | $40/mo | $40/mo |
| **Cost at 10 ch** | $289/mo | **$271/mo** | $307/mo |
| **Max channels** | ~15 | ~50 | **Unlimited** |
| **Fault isolation** | ❌ None | ✅ Services | ✅ Complete |
| **Plug-in/plug-out** | ❌ No | ✅ Yes | ✅ Yes |
| **Visual debugging** | ✅ n8n UI | ✅ n8n UI | ⚠️ Temporal UI |
| **Learning curve** | Low | Medium | High |
| **Scalability** | Low | High | **Very High** |
| **Durability** | Low | Medium | **High** |
| **Migration effort** | — | Easy from Monolith | Easy from Hybrid |

### Recommendation Based on Channel Count & Timeline

| Your Plan | Recommended Architecture | Why |
|-----------|------------------------|-----|
| 1-5 channels, first year | **Enhanced Monolith** | Cheapest, fastest to build |
| 5-15 channels, first year | **Enhanced Hybrid** | Best balance of cost and scalability |
| 15-50 channels, first year | **Enhanced Hybrid** → Microservices | Start hybrid, migrate when needed |
| 50+ channels from start | **Microservices** | Only option that scales this far |

### The Pragmatic Path (Recommended)

```
Month 1-6:   Enhanced Monolith ($29-40/mo, 1-3 channels)
             → Prove the system works, validate content quality

Month 6-12:  Enhanced Hybrid ($60-271/mo, 3-10 channels)
             → Extract services, add PostgreSQL, add caching

Month 12+:   Microservices (if scaling to 50+ channels)
             → Migrate Temporal, full distributed system
             → OR stay on Hybrid if <50 channels (it works fine)
```

This path minimizes risk, cost, and time-to-market while preserving the option to scale.
