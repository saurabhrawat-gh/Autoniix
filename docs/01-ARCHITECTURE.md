# System Architecture

> Temporal microservices | Python FastAPI | PostgreSQL + Redis + MinIO | Traefik gateway

---

## Temporal Server Topology

```
┌────────────────────────────────────────────────────┐
│              Temporal Cluster (Docker)             │
│                                                    │
│  ┌──────────────────┐  ┌─────────────────────────┐ │
│  │ temporal-server   │  │ temporal-admin-tools     │ │
│  │                   │  │ (CLI, namespace setup)   │ │
│  │ Frontend Service  │  └─────────────────────────┘ │
│  │ History Service   │                                │
│  │ Matching Service  │  ┌─────────────────────────┐ │
│  │ Worker Service    │  │ temporal-ui              │ │
│  │                   │  │ (Web dashboard)          │ │
│  └────────┬──────────┘  │ Port: 8080              ││
│  ┌────────▼──────────┐                             │
│  │ postgres-temporal  │  Temporal persistence DB   │
│  └───────────────────┘                             │
└────────────────────────────────────────────────────┘
```

Temporal requires its **own PostgreSQL database** (separate from the application database). Both can run on the same PostgreSQL instance as different logical databases:
- `temporal` — Temporal persistence
- `temporal_visibility` — Temporal search/visibility
- `autoniix` — Application data

---

## Service Catalog

### 10 Microservices

| # | Service | Port | Language | Purpose | Scaling |
|---|---------|------|----------|---------|---------|
| 1 | **Research** | 5001 | Python/FastAPI | Topic research, competitor analysis, fact gathering | Horizontal |
| 2 | **Script** | 5002 | Python/FastAPI | Script writing, critique, rewrite, hooks, metadata | Horizontal |
| 3 | **Voice** | 5003 | Python/FastAPI | TTS generation via provider interface (Fish Audio default) | Horizontal (rate-limited by provider) |
| 4 | **Assets** | 5004 | Python/FastAPI | Stock footage, music, SFX search + scoring + dedup | Horizontal |
| 5 | **Thumbnail** | 5005 | Python/FastAPI | Concept generation, DALL-E rendering, QC | Limited by DALL-E rate |
| 6 | **Assembly** | 5006 | Python/FastAPI | Direction Engine, v3 JSON, 30+ quality gates, compliance | Horizontal |
| 7 | **Render** | 4000 | TypeScript/Express | Remotion video rendering (separate repo) | Add VPS instances |
| 8 | **Delivery** | 5007 | Python/FastAPI | YouTube upload, metadata injection, AI disclosure | Horizontal |
| 9 | **Analytics** | 5008 | Python/FastAPI | YouTube API analytics, pattern detection, insights | Vertical (cron) |
| 10 | **Admin** | 5009 | Python/FastAPI | REST API for channels, config, controls, audit | Vertical (low traffic) |

### Temporal Workers

Workers are Python processes that poll Temporal task queues and execute activities:

| Worker | Task Queue | Activities |
|--------|------------|------------|
| `production-worker` | `video-production` | research, script, voice, assets, thumbnail, assembly |
| `render-worker` | `video-render` | render (calls Remotion API), delivery |
| `analytics-worker` | `analytics` | analytics, trend scan |
| `scheduler-worker` | `scheduler` | channel eligibility, schedule checks |

Workers call services via HTTP (localhost or Docker network). This separation means:
- Workers handle Temporal protocol (polling, heartbeats, retries)
- Services handle business logic (AI calls, data processing)
- Services can be tested independently (curl, pytest)

---

## Data Layer

### PostgreSQL Schema (Application Database: `autoniix`)

```sql
-- Channels: all channel configuration and DNA
CREATE TABLE channels (
    id              VARCHAR(20) PRIMARY KEY,        -- e.g., BS001
    channel_name    VARCHAR(200) NOT NULL,
    niche           VARCHAR(50) NOT NULL,
    sub_niche       VARCHAR(100),
    youtube_id      VARCHAR(30),
    config          JSONB NOT NULL,                 -- All Channel_DNA columns (63+)
    voice_config    JSONB NOT NULL,                 -- voice_id, provider, wpm, profile
    brand_config    JSONB NOT NULL,                 -- colors, fonts, intro/outro
    status          VARCHAR(20) DEFAULT 'active',   -- active | paused | disabled
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Videos: production pipeline state and artifacts
CREATE TABLE videos (
    id                  VARCHAR(50) PRIMARY KEY,    -- VID_BS001_20250425_001
    channel_id          VARCHAR(20) REFERENCES channels(id),
    temporal_workflow_id VARCHAR(200),               -- Temporal workflow run ID
    status              VARCHAR(30) NOT NULL,        -- researching | scripting | rendering | delivered | failed
    content_mode        VARCHAR(20),                 -- long_form | short_form
    topic               TEXT,
    scores              JSONB,                       -- All quality scores per gate
    artifacts           JSONB,                       -- URLs: script, audio, video, thumbnail
    metadata            JSONB,                       -- Title, description, tags
    checkpoint          VARCHAR(50),                 -- Last completed step
    total_cost          DECIMAL(8,4) DEFAULT 0,
    content_fingerprint TEXT,                        -- For cross-channel dedup
    error_log           JSONB,                       -- Error history
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY HASH (channel_id);

-- Create 10 partitions for scale
CREATE TABLE videos_p0 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 0);
CREATE TABLE videos_p1 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 1);
CREATE TABLE videos_p2 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 2);
CREATE TABLE videos_p3 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 3);
CREATE TABLE videos_p4 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 4);
CREATE TABLE videos_p5 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 5);
CREATE TABLE videos_p6 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 6);
CREATE TABLE videos_p7 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 7);
CREATE TABLE videos_p8 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 8);
CREATE TABLE videos_p9 PARTITION OF videos FOR VALUES WITH (MODULUS 10, REMAINDER 9);

CREATE INDEX idx_videos_status ON videos(channel_id, status);
CREATE INDEX idx_videos_fingerprint ON videos(content_fingerprint);
CREATE INDEX idx_videos_created ON videos(created_at DESC);
CREATE INDEX idx_videos_workflow ON videos(temporal_workflow_id);

-- Beliefs: belief registry for content diversity
CREATE TABLE beliefs (
    id              SERIAL PRIMARY KEY,
    channel_id      VARCHAR(20) REFERENCES channels(id),
    category        VARCHAR(50) NOT NULL,
    belief_text     TEXT NOT NULL,
    evidence_level  VARCHAR(20),                    -- proven | emerging | debated
    times_used      INT DEFAULT 0,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_beliefs_channel ON beliefs(channel_id, category);

-- Performance memory: what works per channel
CREATE TABLE performance_memory (
    id              SERIAL PRIMARY KEY,
    channel_id      VARCHAR(20) REFERENCES channels(id),
    metric_type     VARCHAR(50) NOT NULL,           -- ctr | retention | watch_time
    pattern         JSONB NOT NULL,                 -- What was tried
    result          JSONB NOT NULL,                 -- What happened
    confidence      DECIMAL(3,2),
    still_valid     BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ
);

-- Prompt registry: versioned prompt templates
CREATE TABLE prompts (
    id              SERIAL PRIMARY KEY,
    prompt_key      VARCHAR(100) UNIQUE NOT NULL,   -- e.g., research.synthesis.v3
    template        TEXT NOT NULL,
    model_hint      VARCHAR(50),                    -- Recommended model
    version         INT DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- API usage tracking: cost accounting
CREATE TABLE api_usage (
    id              SERIAL PRIMARY KEY,
    video_id        VARCHAR(50) REFERENCES videos(id),
    provider        VARCHAR(50) NOT NULL,           -- openai | anthropic | google | fish_audio
    model           VARCHAR(50),
    tokens_in       INT,
    tokens_out      INT,
    bytes_charged   INT,                            -- For TTS (Fish Audio)
    cost_usd        DECIMAL(8,6) NOT NULL,
    latency_ms      INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_usage_video ON api_usage(video_id);
CREATE INDEX idx_api_usage_provider ON api_usage(provider, created_at);

-- Trend intelligence
CREATE TABLE trends (
    id              SERIAL PRIMARY KEY,
    niche           VARCHAR(50) NOT NULL,
    trend_data      JSONB NOT NULL,
    source          VARCHAR(50),                    -- youtube | google_trends | reddit
    scanned_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ
);

-- Audit log: every significant action
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor           VARCHAR(100) NOT NULL,          -- system | admin:user@email | workflow:id
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     VARCHAR(100),
    details         JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- System config: global settings
CREATE TABLE system_config (
    config_key      VARCHAR(100) PRIMARY KEY,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed essential config
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('system_status', 'active', 'Global system status: active | paused | maintenance'),
    ('emergency_stop', 'false', 'Emergency stop flag'),
    ('max_concurrent_runs', '3', 'Max concurrent video productions'),
    ('daily_budget_limit', '50.00', 'Daily API spend cap in USD'),
    ('default_tts_provider', 'fish_audio', 'Default TTS provider key'),
    ('default_llm_provider', 'openai', 'Default LLM provider key'),
    ('default_search_provider', 'serpapi', 'Default search provider key'),
    ('default_image_provider', 'dalle', 'Default image generation provider key'),
    ('default_storage_provider', 'minio', 'Default object storage provider key');
```

### Redis Key Patterns

```
# Caching (reduces API costs)
cache:research:{channel}:{topic_hash}       → JSON      TTL: 7 days
cache:competitor:{channel_id}               → JSON      TTL: 24 hours
cache:asset:{search_term_hash}              → JSON      TTL: 30 days
cache:trend:{niche}:{date}                  → JSON      TTL: 12 hours
cache:voice:{text_hash}:{voice_id}          → audio_url TTL: 90 days

# Rate limiting (per provider)
ratelimit:openai:{minute}                   → counter   TTL: 60s
ratelimit:anthropic:{minute}                → counter   TTL: 60s
ratelimit:fish_audio:{minute}               → counter   TTL: 60s
ratelimit:serpapi:{day}                     → counter   TTL: 24h
ratelimit:dalle:{minute}                    → counter   TTL: 60s

# Deduplication (cross-channel)
dedup:topic:{hash}                          → channel_id    TTL: 90 days
dedup:asset:{hash}                          → video_id      TTL: 30 days
dedup:fingerprint:{hash}                    → video_id      TTL: 365 days

# Execution locks (prevent double-runs)
lock:channel:{channel_id}                   → workflow_id   TTL: 24h

# Circuit breakers (per provider)
circuit:{provider}:failures                 → count    TTL: 10 min
circuit:{provider}:last_failure             → timestamp
circuit:{provider}:state                    → closed | open | half_open
```

### MinIO Bucket Structure

```
yt-automation/
├── scripts/
│   └── {channel_id}/{video_id}/
│       ├── script_base.json          # Canonical script
│       ├── script_voice.json         # Voiceover view
│       ├── script_assets.json        # Asset view
│       └── script_remotion.json      # Remotion v3 direction
├── audio/
│   └── {channel_id}/{video_id}/
│       ├── scene_{id}.mp3            # Per-scene TTS
│       └── full_narration.mp3        # Merged audio
├── assets/
│   └── {channel_id}/{video_id}/
│       ├── stock_{id}.mp4            # Stock footage
│       ├── music.mp3                 # Background music
│       └── sfx_{id}.mp3             # Sound effects
├── thumbnails/
│   └── {channel_id}/{video_id}/
│       ├── concept_{n}.png           # DALL-E backgrounds
│       └── final.png                 # Selected thumbnail
├── renders/
│   └── {channel_id}/{video_id}/
│       ├── video.mp4                 # Final rendered video
│       └── short.mp4                 # Short-form variant
└── backups/
    └── {date}/
        └── pg_dump.sql.gz
```

---

## Network Topology

### Docker Compose Network

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Network: autoniix-net                   │
│                                                          │
│  PUBLIC (via Traefik):                                   │
│    - Traefik         :443 / :80                          │
│    - Temporal UI     :8080 (optional, auth-gated)        │
│    - Admin API       :5009 (behind Traefik with JWT)     │
│                                                          │
│  INTERNAL ONLY (not exposed):                            │
│    - temporal-server :7233 (gRPC)                        │
│    - research        :5001                               │
│    - script          :5002                               │
│    - voice           :5003                               │
│    - assets          :5004                               │
│    - thumbnail       :5005                               │
│    - assembly        :5006                               │
│    - delivery        :5007                               │
│    - analytics       :5008                               │
│    - postgres-app    :5432                               │
│    - postgres-temp   :5433                               │
│    - redis           :6379                               │
│    - minio           :9000 / :9001 (console)             │
│                                                          │
│  SEPARATE VPS (at scale):                                │
│    - remotion        :4000 (same network or VPN)         │
└─────────────────────────────────────────────────────────┘
```

All inter-service communication is over the Docker bridge network. Only Traefik is publicly exposed. Services reference each other by Docker service name (e.g., `http://research:5001`).

---

## Security Model

| Layer | Mechanism | Details |
|-------|-----------|---------|
| **Gateway** | Traefik + Let's Encrypt | Auto TLS, HSTS, rate limiting |
| **Service auth** | JWT (internal) | Workers/services pass signed tokens; validate per-request |
| **Admin auth** | JWT + RBAC | Roles: admin, operator, viewer |
| **Secrets** | Docker secrets / `.env` | Never in code or docs; Vault roadmap |
| **Network** | Docker internal network | Services not publicly reachable |
| **mTLS** | Roadmap (phase 2) | Between services for zero-trust |
| **Audit** | `audit_log` table | Every action logged with actor, resource, timestamp |
| **Input validation** | Pydantic models | All service inputs validated at boundary |
| **Prompt injection** | Sanitization layer | Strip control characters, validate patterns |

See `docs/08-SECURITY.md` for full security documentation.

---

## Provider Abstraction Layer

Every external API call goes through an abstract provider interface:

```
┌──────────────┐     ┌──────────────────────────────────┐
│ Temporal      │     │  Provider Registry (config.yaml)  │
│ Activity      │────▶│                                    │
│              │     │  tts: fish_audio                   │
└──────────────┘     │  llm.research: google              │
                     │  llm.script: anthropic              │
                     │  llm.factcheck: openai              │
                     │  search: serpapi                     │
                     │  image: dalle                        │
                     │  storage: minio                      │
                     └──────────┬───────────────────────────┘
                                │
                     ┌──────────▼───────────────────────┐
                     │  Abstract Base Class              │
                     │  (e.g., TTSProvider)              │
                     │                                    │
                     │  ├── FishAudioTTS                  │
                     │  ├── ElevenLabsTTS                 │
                     │  └── GoogleTTS                     │
                     └────────────────────────────────────┘
```

Swapping a provider = change one env var or config key + ensure the implementation file exists. See `docs/11-PROVIDER-INTERFACES.md` for full interface definitions.

---

## Request Flow (Single Video Production)

```
1. DailySchedulerWorkflow (cron every 6h)
   → Check system status, budget, emergency stop
   → Query active channels with matching schedule
   → For each eligible channel:
       → Start child VideoProductionWorkflow

2. VideoProductionWorkflow
   ├─ research_activity     → Research Service :5001   → research_package
   ├─ script_activity       → Script Service :5002     → script_base + metadata
   ├─ PARALLEL:
   │  ├─ voice_activity     → Voice Service :5003      → scene audio + timestamps
   │  ├─ assets_activity    → Assets Service :5004     → asset manifest
   │  └─ thumbnail_activity → Thumbnail Service :5005  → thumbnail variants
   ├─ assembly_activity     → Assembly Service :5006   → v3 JSON + QA report
   ├─ QUALITY GATE (≥ 8.0 or signal for human review)
   ├─ render_activity       → Remotion :4000           → rendered video
   └─ delivery_activity     → Delivery Service :5007   → YouTube upload

3. Post-production
   └─ Update PostgreSQL (video status, costs, artifacts)
   └─ Send notification (webhook / email)
```
