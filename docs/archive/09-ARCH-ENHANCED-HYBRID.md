# Architecture Option 1: Enhanced Hybrid (n8n + Lightweight Services)

> Self-hosted n8n | Fish Audio TTS | PostgreSQL | Docker services on same VPS
> Build time: 5-6 weeks | Best for: 1-50 channels

---

## Overview

n8n remains the **orchestrator** (~50 lightweight nodes total) while heavy processing is extracted into **Docker containers** running alongside n8n on the same VPS. n8n calls these services via HTTP — exactly what it's designed for.

**Key decisions:**
- **Voice:** Fish Audio (replaces ElevenLabs) — 70-85% cheaper
- **Database:** PostgreSQL (replaces Google Sheets) — no rate limits, indexing, transactions
- **Infrastructure:** Self-hosted on Hetzner — n8n + services + DB on same VPS
- **Rendering:** Remotion self-hosted (same or separate VPS depending on scale)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Single Hetzner VPS (Docker Compose)        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │               n8n (Orchestrator)                      │   │
│  │                                                        │   │
│  │  Workflow A: Control & Scheduling      (~20 nodes)    │   │
│  │  Workflow B: Production Pipeline       (~15 nodes)    │   │
│  │  Workflow C: Delivery                  (~8 nodes)     │   │
│  │  Workflow D: Intelligence (cron)       (~5 nodes)     │   │
│  │  Admin Webhook                         (~5 nodes)     │   │
│  │                                                        │   │
│  │  Total: ~53 nodes (down from 582)                     │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                         │ HTTP calls (localhost)             │
│    ┌────────────────────┼────────────────────────┐          │
│    │                    │                        │          │
│  ┌─▼──────────┐  ┌─────▼──────┐  ┌─────────────▼──┐       │
│  │ Research    │  │ Script     │  │ Assembly       │       │
│  │ Service     │  │ Service    │  │ Service        │       │
│  │ (Python)    │  │ (Python)   │  │ (Python)       │       │
│  └────────────┘  └────────────┘  └────────────────┘       │
│    ┌────────────┐  ┌────────────┐  ┌────────────────┐       │
│    │ Voice      │  │ Assets     │  │ Thumbnail      │       │
│    │ Service    │  │ Service    │  │ Service         │       │
│    │ (Fish API) │  │ (Python)   │  │ (Python)        │       │
│    └────────────┘  └────────────┘  └────────────────┘       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ PostgreSQL   │  │ Redis        │  │ Remotion      │      │
│  │ (Database)   │  │ (Cache)      │  │ (Renderer)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Can This Work on the Current Architecture?

**Yes — and this is the recommended approach.** Here's how:

The "hybrid" isn't a different architecture — it's the **same n8n setup** with heavy logic extracted into Docker containers on the same VPS. n8n's HTTP Request node calls `http://localhost:5001/research`, `http://localhost:5002/script`, etc.

**What stays in n8n:**
- Scheduling, routing, conditionals, error handling
- Checkpoint management, pause/resume
- Google Sheets → PostgreSQL reads/writes (via n8n's built-in PostgreSQL node)
- Webhook triggers between workflows

**What moves to Docker services:**
- LLM API calls (batching, retries, caching)
- Fish Audio TTS generation
- Stock footage search + relevance scoring
- Thumbnail generation (DALL-E + Remotion)
- Direction Engine + v3 generation
- Quality gate evaluation (all 30+ gates)

**Why this works:**
- n8n natively supports HTTP Request nodes (it's designed for this)
- Docker containers run on `localhost` (zero network latency)
- Services are stateless — easy to restart, no data loss
- Each service has its own error handling + retries
- Services can be replaced independently (plug-in/plug-out)

---

## Simplified n8n Workflows

### Workflow A: Control & Scheduling (~20 nodes)

```
Schedule Trigger (6h)
  → Read System_Config (PostgreSQL)
  → System Status Gate
  → Read Channel_DNA (PostgreSQL)
  → Filter Active Channels
  → Check Schedule + Timezone
  → Check Execution Locks
  → Loop Channels (splitInBatches)
    → Budget Pre-Check
    → Generate Run Metadata
    → Write Execution Lock
    → Trigger Workflow B (webhook)
  → Watchdog Check (stuck > 6h)
```

### Workflow B: Production Pipeline (~15 nodes)

```
Webhook Trigger
  → HTTP POST localhost:5001/research    → Research JSON
  → HTTP POST localhost:5002/script      → Script + Metadata
  → Split Parallel:
    ├→ HTTP POST localhost:5003/voice     → Audio + Timestamps
    ├→ HTTP POST localhost:5004/assets    → Asset Manifest
    └→ HTTP POST localhost:5005/thumbnail → Thumbnail Variants
  → Merge Results
  → HTTP POST localhost:5006/assembly    → v3 JSON + QA Report
  → Quality Gate Check (IF score ≥ 8.0)
    → HTTP POST localhost:5007/render    → Submit Render Job
  → Update Database (PostgreSQL)
  → Send Notification
```

### Workflow C: Delivery (~8 nodes)

```
Remotion Callback Webhook
  → Parse Status
  → IF Success:
    → Download to Storage
    → Build Upload Package (metadata, disclaimers, AI disclosure)
    → Update Database
    → Send Notification
  → IF Failed:
    → Log Failure + Retry with simplified v3
```

### Workflow D: Intelligence (cron, ~5 nodes)

```
Weekly Cron
  → HTTP POST localhost:5008/analytics   → Patterns + Insights
  → Update Performance_Memory (PostgreSQL)
  → Send Insight Report
```

### Admin Webhook (~5 nodes)

```
Webhook /admin/*
  → Auth Check
  → Route: pause/resume/stop/status/budget
  → Update Database
  → Response
```

---

## Service Definitions (Docker Containers)

### Service 1: Research Service (Port 5001)
- **Tech:** Python FastAPI (~300 lines)
- **Endpoints:** `POST /research`
- **Handles:** YouTube API, SerpAPI, Reddit, Wikipedia, News API
- **LLM calls:** Gemini Flash (research synthesis), GPT-4o (fact verification)
- **Caching:** Redis (7-day TTL for competitor data, trends)
- **Output:** `{ research_package, sources, fact_scores }`

### Service 2: Script Service (Port 5002)
- **Tech:** Python FastAPI (~500 lines)
- **Endpoints:** `POST /script`
- **Handles:** Ideation (10 titles), script generation (Claude), critique (GPT-4o-mini), hooks, metadata
- **Retry logic:** Max 2 rewrites built-in
- **Output:** `{ script_v2, metadata, quality_scores }`

### Service 3: Voice Service (Port 5003)
- **Tech:** Python FastAPI (~250 lines)
- **Endpoints:** `POST /voice`
- **Handles:** Emotion mapping (GPT-4o-mini), Fish Audio TTS with timestamps
- **Fish Audio integration:** API calls with credit tracking
- **Output:** `{ audio_files[], timestamps[], duration }`

### Service 4: Assets Service (Port 5004)
- **Tech:** Python FastAPI (~300 lines)
- **Endpoints:** `POST /assets`
- **Handles:** Pixabay/Pexels search, Freesound music/SFX, relevance scoring
- **Caching:** Redis (asset dedup cache, 30-day TTL)
- **Output:** `{ asset_manifest, music_manifest }`

### Service 5: Thumbnail Service (Port 5005)
- **Tech:** Python FastAPI (~200 lines)
- **Endpoints:** `POST /thumbnail`
- **Handles:** Concept generation, DALL-E backgrounds, Remotion rendering
- **Output:** `{ thumbnail_variants[], best_thumbnail }`

### Service 6: Assembly Service (Port 5006)
- **Tech:** Python FastAPI (~400 lines)
- **Endpoints:** `POST /assembly`
- **Handles:** Direction Engine (GPT-4o), v3 JSON generation, all 30 quality gates, compliance
- **Output:** `{ v3_json, quality_report, compliance_report }`

### Service 7: Render Service (Port 5007)
- **Tech:** Node.js Express (~200 lines) wrapping Remotion
- **Endpoints:** `POST /render`, `GET /render/:id`, `GET /health`
- **Handles:** Render queue, status polling, callback to n8n
- **Output:** `{ render_id, status, video_url }`

### Service 8: Analytics Service (Port 5008)
- **Tech:** Python FastAPI (~300 lines)
- **Endpoints:** `POST /analytics`, `POST /trends`
- **Handles:** YouTube Analytics, pattern analysis, trend detection, Performance_Memory
- **Output:** `{ insights, patterns, trend_opportunities }`

---

## Data Layer

### PostgreSQL Tables (replaces 10 Google Sheet tabs)

```sql
-- Core tables
channels          -- Channel_DNA (63 columns)
execution_locks   -- Prevent duplicate runs
videos            -- Output_Log (49 columns) + Feedback_Loop
beliefs           -- Belief_Registry
performance       -- Performance_Memory
prompts           -- Prompt_Registry
trends            -- Trend_Intelligence
api_usage         -- API_Usage_Tracker
system_config     -- System_Config

-- Indexes for fast queries
CREATE INDEX idx_videos_channel_status ON videos(channel_id, status);
CREATE INDEX idx_videos_fingerprint ON videos(content_fingerprint);
CREATE INDEX idx_trends_niche_date ON trends(niche, detected_at);
CREATE INDEX idx_beliefs_channel ON beliefs(channel_id, belief_status);
```

### Redis Cache
- Research results (7-day TTL)
- Asset dedup hashes (30-day TTL)
- Competitor data (24-hour TTL)
- Rate limit counters (per API provider)

---

## Fish Audio Integration

### Plan Selection by Channel Count

| Channels | Plan | Price/month | Credits/month | Usage (Month 3+) | Headroom |
|----------|------|------------|---------------|-------------------|----------|
| 1 | Plus | $11 | 250,000 | ~49,400 | 80% free |
| 3 | Plus | $11 | 250,000 | ~148,200 | 41% free |
| 5 | Plus | $11 | 250,000 | ~247,000 | 1% free |
| 10 | Pro | $75 | 2,000,000 | ~494,000 | 75% free |

### Credit Calculation

```
Per minute of audio ≈ 625 credits

Long-form (8 min audio):  8 × 625 = 5,000 credits/video
Short-form (45 sec audio): 0.75 × 625 = 469 credits/video

Per channel per month (Month 3+: 2L + 3S/week):
  Long:  8.66 videos × 5,000 = 43,300 credits
  Short: 12.99 videos × 469  = 6,093 credits
  Total: ~49,393 credits/channel/month
```

### Fish Audio vs ElevenLabs Cost Comparison

| Channels | Fish Audio | ElevenLabs | Savings |
|----------|-----------|-----------|---------|
| 1 | $11/mo (Plus) | $99/mo (Pro) | **$88/mo (89%)** |
| 3 | $11/mo (Plus) | $99/mo (Pro) | **$88/mo (89%)** |
| 5 | $11/mo (Plus) | $99/mo (Pro, at limit) | **$88/mo (89%)** |
| 10 | $75/mo (Pro) | $330/mo (Scale) | **$255/mo (77%)** |

### Self-Hosted Option (Fish Speech, Apache 2.0)

For maximum savings, self-host the open-source Fish Speech model:
- **CPU mode:** Free, but ~10-30x slower than real-time (8 min audio → 80-240 min)
- **GPU VPS:** ~$40-60/month (RunPod/Vast.ai) for fast inference
- **Recommendation:** Use Fish Audio API (Plus/Pro plan) — the cost is already minimal

---

## Docker Compose Setup

```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n
    ports: ["5678:5678"]
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
    volumes: ["n8n_data:/home/node/.n8n"]
    depends_on: [postgres, redis]

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: yt_automation
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["pg_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    volumes: ["redis_data:/data"]

  research-service:
    build: ./services/research
    ports: ["5001:5001"]
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@postgres/yt_automation

  script-service:
    build: ./services/script
    ports: ["5002:5002"]

  voice-service:
    build: ./services/voice
    ports: ["5003:5003"]
    environment:
      - FISH_AUDIO_API_KEY=${FISH_AUDIO_KEY}

  assets-service:
    build: ./services/assets
    ports: ["5004:5004"]

  thumbnail-service:
    build: ./services/thumbnail
    ports: ["5005:5005"]

  assembly-service:
    build: ./services/assembly
    ports: ["5006:5006"]

  remotion:
    build: ./services/remotion
    ports: ["5007:3000"]

  analytics-service:
    build: ./services/analytics
    ports: ["5008:5008"]
```

---

## Cost Estimation

### Baseline: Per-Video Costs (unchanged from original architecture)

| Component | Long-form | Short-form |
|-----------|----------|-----------|
| GPT-4o (v3, direction, fact-check) | $0.35 | — |
| Claude Sonnet (script, audience sim) | $0.16 | $0.12 |
| Gemini Flash (research, QC, ~18 calls) | $0.05 | $0.03 |
| GPT-4o-mini (tags, desc, critique) | $0.04 | $0.02 |
| GPT-4o Vision (thumbnail QC) | $0.05 | — |
| DALL-E 3 (2 thumbnails) | $0.08 | — |
| SerpAPI (3 queries) | $0.03 | $0.03 |
| Fish Audio (included in plan) | $0.00 | $0.00 |
| **LLM + API total per video** | **$0.76** | **$0.20** |

> Note: Shorts are cheaper than original $0.31 because Fish Audio plan pricing is lower,
> and shorts skip some expensive nodes (thumbnail QC, direction engine).

### Monthly Video Output per Channel

| Phase | Long-form/month | Shorts/month | Total videos |
|-------|----------------|-------------|-------------|
| Month 1-2 (1L + 7S/week) | 4.33 | 30.3 | 34.63 |
| Month 3+ (2L + 3S/week) | 8.66 | 12.99 | 21.65 |

### Monthly LLM/API Variable Cost per Channel

| Phase | Long-form cost | Shorts cost | Total/channel |
|-------|---------------|------------|---------------|
| Month 1-2 | 4.33 × $0.76 = $3.29 | 30.3 × $0.20 = $6.06 | **$9.35** |
| Month 3+ | 8.66 × $0.76 = $6.58 | 12.99 × $0.20 = $2.60 | **$9.18** |

### Complete Cost: 1 Channel

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + DB + services + Remotion) | $18 | $18 | All-in-one VPS |
| Fish Audio Plus | $11 | $11 | 250K credits, 80% headroom |
| LLM variable | $9.35 | $9.18 | Per channel |
| SerpAPI | $0 | $0 | Free tier (100 searches) |
| Misc (domain, monitoring) | $2 | $2 | |
| **TOTAL** | **$40** | **$40** | |

### Complete Cost: 3 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (all-in-one) | $18 | $18 | Still fits on single VPS |
| Fish Audio Plus | $11 | $11 | 250K credits, 41% headroom at steady |
| LLM variable (×3) | $28.05 | $27.54 | |
| SerpAPI | $0 | $0 | Free tier (~195 searches, tight) |
| Misc | $3 | $3 | |
| **TOTAL** | **$60** | **$60** | **$20/channel** |

### Complete Cost: 5 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + DB + services) | $18 | $18 | |
| Hetzner CX21 (Remotion dedicated) | $7 | $7 | Separate render server |
| Fish Audio Plus | $11 | $11 | At limit month 3+ (247K/250K) |
| LLM variable (×5) | $46.75 | $45.90 | |
| SerpAPI Basic | $50 | $50 | 5K searches (325 needed) |
| Misc | $5 | $5 | |
| **TOTAL** | **$138** | **$137** | **$27/channel** |

### Complete Cost: 10 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + DB + services) | $18 | $18 | |
| Hetzner CX31 (Remotion dedicated) | $24 | $24 | More render capacity |
| Fish Audio Pro | $75 | $75 | 2M credits, 75% headroom |
| LLM variable (×10) | $93.50 | $91.80 | |
| SerpAPI Basic | $50 | $50 | 5K searches (650 needed) |
| Misc | $10 | $10 | |
| **TOTAL** | **$271** | **$269** | **$27/channel** |

### Cost Summary Table

| Channels | Monthly Cost | Per Channel | vs Original (ElevenLabs) | Savings |
|----------|-------------|------------|--------------------------|---------|
| **1** | **$40** | $40 | ~$142* | **72%** |
| **3** | **$60** | $20 | ~$178* | **66%** |
| **5** | **$138** | $28 | ~$230* | **40%** |
| **10** | **$271** | $27 | ~$328 | **17%** |

> *Original estimates assumed ElevenLabs Pro $99 and SerpAPI $50 even at 1 channel.
> Hybrid saves most at small scale by right-sizing every component.

### Cumulative Cost (First 12 Months, 1 Channel)

| Month | Monthly Cost | Cumulative | Revenue Estimate | Net |
|-------|-------------|-----------|-----------------|-----|
| 1-2 | $40 | $80 | $0 | -$80 |
| 3-4 | $40 | $160 | $0 | -$160 |
| 5-6 | $40 | $240 | $0-50 | -$190 |
| 7-9 | $40 | $360 | $50-200 | -$160 |
| 10-12 | $40 | $480 | $100-400 | -$80 to +$320 |

---

## Pros & Cons

### Pros
- ✅ **Cheapest production-ready option** ($40/mo for 1 channel)
- ✅ Keep familiar n8n UI for workflow visualization
- ✅ Fault-isolated services (one crash doesn't break others)
- ✅ Plug-in/plug-out services (swap voice provider, LLM, etc.)
- ✅ PostgreSQL eliminates Sheets rate limits and data issues
- ✅ Redis caching reduces API costs over time
- ✅ All runs on a single VPS (up to 5 channels)
- ✅ Fish Audio = 77-89% cheaper than ElevenLabs
- ✅ Build time: 5-6 weeks
- ✅ Easy migration to full microservices later

### Cons
- ⚠️ n8n is still a single point of failure (mitigated by Docker restart policies)
- ⚠️ Needs Docker/Docker Compose knowledge
- ⚠️ 8 Python services to maintain (but each is simple, 200-500 lines)
- ⚠️ Single VPS may struggle above 5 channels (need to split)
- ⚠️ No built-in distributed tracing (add later if needed)

---

## Build Timeline

| Week | Deliverable |
|------|------------|
| 1 | Docker Compose stack, PostgreSQL schema, Redis, n8n config |
| 2 | Research Service + Script Service (core pipeline) |
| 3 | Voice Service (Fish Audio) + Assets Service |
| 4 | Assembly Service + Render Service (Remotion) |
| 5 | n8n Workflows (A, B, C, D, Admin) + Thumbnail Service |
| 6 | Quality gates, compliance, testing, first video published |

---

## Scaling Path

| Channels | Infrastructure Change | Cost Impact |
|----------|-----------------------|-------------|
| 1-5 | Single CX31 VPS | $40-138/mo |
| 5-10 | Add dedicated Remotion VPS | +$7-24/mo |
| 10-25 | Upgrade to CX41, add Redis VPS | +$20/mo |
| 25-50 | Split services to 2 VPS, multiple Remotion workers | +$50/mo |
| 50+ | Consider migration to Kubernetes / Temporal | Architecture change |
