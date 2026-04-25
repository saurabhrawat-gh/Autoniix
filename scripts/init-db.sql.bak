-- ============================================================
-- YT Automation — Application Database Schema
-- ============================================================

-- ── Channels ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channels (
    channel_id       VARCHAR(10)   PRIMARY KEY,
    channel_name     VARCHAR(255)  NOT NULL,
    niche            VARCHAR(100)  NOT NULL,
    youtube_channel_id VARCHAR(50),
    content_mode     VARCHAR(20)   DEFAULT 'long_form',
    voice_id         VARCHAR(100),
    brand_config     JSONB         DEFAULT '{}',
    channel_dna      JSONB         DEFAULT '{}',
    performance_memory JSONB       DEFAULT '{}',
    schedule_config  JSONB         DEFAULT '{"cadence_long": 2, "cadence_short": 3}',
    status           VARCHAR(20)   DEFAULT 'active',
    created_at       TIMESTAMPTZ   DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Videos ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
    id               BIGSERIAL     PRIMARY KEY,
    content_id       VARCHAR(100)  UNIQUE NOT NULL,
    channel_id       VARCHAR(10)   REFERENCES channels(channel_id),
    status           VARCHAR(30)   DEFAULT 'pending',
    content_mode     VARCHAR(20),
    title            TEXT,
    topic            TEXT,
    script_base      JSONB         DEFAULT '{}',
    scores           JSONB         DEFAULT '{}',
    quality_report   JSONB         DEFAULT '{}',
    voice_result     JSONB         DEFAULT '{}',
    asset_manifest   JSONB         DEFAULT '{}',
    thumbnail_result JSONB         DEFAULT '{}',
    v3_direction     JSONB         DEFAULT '{}',
    render_result    JSONB         DEFAULT '{}',
    delivery_result  JSONB         DEFAULT '{}',
    youtube_video_id VARCHAR(50),
    total_cost       DECIMAL(10,4) DEFAULT 0,
    content_fingerprint VARCHAR(64),
    idempotency_key  VARCHAR(100),
    workflow_id      VARCHAR(200),
    error_message    TEXT,
    created_at       TIMESTAMPTZ   DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ── API Usage ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_usage (
    id               BIGSERIAL     PRIMARY KEY,
    content_id       VARCHAR(100),
    service          VARCHAR(50)   NOT NULL,
    provider         VARCHAR(50)   NOT NULL,
    model            VARCHAR(100),
    tokens_in        INTEGER       DEFAULT 0,
    tokens_out       INTEGER       DEFAULT 0,
    cost_usd         DECIMAL(10,6) DEFAULT 0,
    latency_ms       INTEGER       DEFAULT 0,
    success          BOOLEAN       DEFAULT TRUE,
    error_message    TEXT,
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ── System Config ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_config (
    config_key       VARCHAR(100)  PRIMARY KEY,
    config_value     TEXT          NOT NULL,
    description      TEXT,
    updated_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Audit Log ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id               BIGSERIAL     PRIMARY KEY,
    actor            VARCHAR(200)  NOT NULL,
    action           VARCHAR(100)  NOT NULL,
    resource_type    VARCHAR(50),
    resource_id      VARCHAR(200),
    details          JSONB         DEFAULT '{}',
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_videos_channel       ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_status        ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created       ON videos(created_at);
CREATE INDEX IF NOT EXISTS idx_videos_fingerprint   ON videos(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_videos_workflow      ON videos(workflow_id);
CREATE INDEX IF NOT EXISTS idx_usage_content        ON api_usage(content_id);
CREATE INDEX IF NOT EXISTS idx_usage_provider       ON api_usage(provider);
CREATE INDEX IF NOT EXISTS idx_usage_created        ON api_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor          ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_created        ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_resource       ON audit_log(resource_type, resource_id);

-- ── Default System Config ───────────────────────────────────
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('system_active',           'true',  'Master on/off switch'),
    ('emergency_stop',          'false', 'Emergency stop flag'),
    ('daily_budget_limit',      '50.00', 'Maximum daily spend in USD'),
    ('quality_threshold',       '8.0',   'Minimum composite quality score'),
    ('human_review_threshold',  '8.0',   'Score below which human review is required'),
    ('max_videos_per_day',      '20',    'Maximum videos to produce per day')
ON CONFLICT (config_key) DO NOTHING;

-- ── Seed: Initial Channels (examples, adjust as needed) ────
INSERT INTO channels (channel_id, channel_name, niche, content_mode) VALUES
    ('BS001', 'Body Signals', 'health', 'long_form')
ON CONFLICT (channel_id) DO NOTHING;
