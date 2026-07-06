-- 001_init.sql — squashed initial schema.
--
-- This file is the union of all migrations from 202605090001 through
-- 202605160001 (18 files), squashed on 2026-05-17. Every statement uses
-- IF NOT EXISTS / ON CONFLICT DO NOTHING / OR REPLACE, so applying this
-- to an empty DB creates the full schema, and applying to an existing
-- DB (already migrated through the 18 originals) is a no-op.
--
-- New migrations should be added as 2026MMDDXXXX_<name>.sql files after
-- this one. The schema_migrations table tracks applied versions by
-- checksum.


-- ===== 202605090001_foundation.sql =====
-- 202605090001_foundation.sql
-- Phase 0: Foundations
-- Adds: schema_migrations tracker, feature_flags, audit_log_v2.
-- All additive. Safe to re-run.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version       VARCHAR(40)   PRIMARY KEY,
    applied_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    checksum      VARCHAR(64)   NOT NULL,
    description   TEXT
);

-- Feature flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id            BIGSERIAL     PRIMARY KEY,
    key           VARCHAR(100)  UNIQUE NOT NULL,
    enabled       BOOLEAN       NOT NULL DEFAULT FALSE,
    description   TEXT,
    payload       JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO feature_flags (key, enabled, description) VALUES
    ('ui.v2.enabled',           FALSE, 'Show /dashboard/v2 routes and v2 components'),
    ('auth.legacy.enabled',     TRUE,  'Allow shared-password login (deprecated)'),
    ('auth.v2.enabled',         FALSE, 'Enable real users / sessions / MFA'),
    ('providers.db_chain.enabled', FALSE, 'Read provider config from DB instead of env'),
    ('review.gate.enabled',     FALSE, 'Pause workflows for human review when channel.human_review_required != never'),
    ('notifications.slack.enabled', FALSE, 'Route notifications to Slack'),
    ('safety.uniqueness_guard.enabled', FALSE, 'Reject videos > 0.92 cosine to last 30 outputs')
ON CONFLICT (key) DO NOTHING;

-- Richer audit log (additive, does not touch existing audit_log)
CREATE TABLE IF NOT EXISTS audit_log_v2 (
    id            BIGSERIAL     PRIMARY KEY,
    actor_user_id INTEGER,
    actor_label   VARCHAR(120),
    action        VARCHAR(100)  NOT NULL,
    target_type   VARCHAR(60)   NOT NULL,
    target_id     VARCHAR(120),
    before        JSONB,
    after         JSONB,
    source        VARCHAR(20)   NOT NULL DEFAULT 'api',
    request_id    VARCHAR(80),
    ip            VARCHAR(45),
    user_agent    TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_log_v2_target_idx
    ON audit_log_v2(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_v2_actor_idx
    ON audit_log_v2(actor_user_id, created_at DESC);

-- ===== 202605090002_channels_v2.sql =====
-- 202605090002_channels_v2.sql
-- Phase 1 (S1): Channel seeding tables + additive columns.
-- Strictly additive: existing channels rows are untouched.
-- A backfill script (scripts/backfill_channel_profiles.py) seeds default
-- profiles for the pre-existing channels.

-- Additive columns on channels
ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS platform                  VARCHAR(40),
    ADD COLUMN IF NOT EXISTS handle                    VARCHAR(120),
    ADD COLUMN IF NOT EXISTS description               TEXT,
    ADD COLUMN IF NOT EXISTS mission                   TEXT,
    ADD COLUMN IF NOT EXISTS vision                    TEXT,
    ADD COLUMN IF NOT EXISTS brand_personality         TEXT,
    ADD COLUMN IF NOT EXISTS target_age_group          VARCHAR(40),
    ADD COLUMN IF NOT EXISTS geography                 VARCHAR(120),
    ADD COLUMN IF NOT EXISTS primary_language          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS secondary_languages       TEXT[],
    ADD COLUMN IF NOT EXISTS humor_style               VARCHAR(60),
    ADD COLUMN IF NOT EXISTS narration_style           VARCHAR(60),
    ADD COLUMN IF NOT EXISTS sound_design_style        VARCHAR(60),
    ADD COLUMN IF NOT EXISTS music_style               VARCHAR(60),
    ADD COLUMN IF NOT EXISTS lut_preference            VARCHAR(60),
    ADD COLUMN IF NOT EXISTS transition_preference     VARCHAR(60),
    ADD COLUMN IF NOT EXISTS typography_preference     VARCHAR(60),
    ADD COLUMN IF NOT EXISTS meme_intensity            SMALLINT,
    ADD COLUMN IF NOT EXISTS emotion_intensity         SMALLINT,
    ADD COLUMN IF NOT EXISTS content_type_tags         TEXT[],
    ADD COLUMN IF NOT EXISTS human_review_ratio        DECIMAL(4,3) DEFAULT 0.000,
    ADD COLUMN IF NOT EXISTS review_timeout_hours      INTEGER      DEFAULT 24,
    ADD COLUMN IF NOT EXISTS authenticity_threshold    DECIMAL(4,3) DEFAULT 0.700,
    ADD COLUMN IF NOT EXISTS source                    VARCHAR(20)  DEFAULT 'seed';

-- Channel profile (extended)
CREATE TABLE IF NOT EXISTS channel_profiles (
    channel_id            VARCHAR(20)   PRIMARY KEY REFERENCES channels(channel_id) ON DELETE CASCADE,
    payload               JSONB         NOT NULL DEFAULT '{}'::jsonb,
    -- Denormalized convenience for filtering; mirrors payload.* values
    mission               TEXT,
    vision                TEXT,
    brand_personality     TEXT,
    tone                  VARCHAR(60),
    completeness_score    SMALLINT      NOT NULL DEFAULT 0,
    last_ai_assist_at     TIMESTAMPTZ,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Pillars
CREATE TABLE IF NOT EXISTS channel_pillars (
    id                    BIGSERIAL     PRIMARY KEY,
    channel_id            VARCHAR(20)   NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    name                  VARCHAR(120)  NOT NULL,
    description           TEXT,
    weight                DECIMAL(4,2)  NOT NULL DEFAULT 1.0,
    examples              JSONB         NOT NULL DEFAULT '[]'::jsonb,
    position              SMALLINT      NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS channel_pillars_channel_idx
    ON channel_pillars(channel_id, position);

-- Topic rules (avoid / safe / core / inspiration / competitor)
CREATE TABLE IF NOT EXISTS channel_topic_rules (
    id                    BIGSERIAL     PRIMARY KEY,
    channel_id            VARCHAR(20)   NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    kind                  VARCHAR(40)   NOT NULL,
    value                 TEXT          NOT NULL,
    source                VARCHAR(40),
    metadata              JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT channel_topic_rules_kind_chk CHECK (kind IN
        ('avoid','safe','core','inspiration_competitor','primary_competitor'))
);
CREATE INDEX IF NOT EXISTS channel_topic_rules_channel_idx
    ON channel_topic_rules(channel_id, kind);

-- References (PDFs / URLs / videos / asset packs)
CREATE TABLE IF NOT EXISTS channel_references (
    id                    BIGSERIAL     PRIMARY KEY,
    channel_id            VARCHAR(20)   NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    kind                  VARCHAR(30)   NOT NULL,
    label                 VARCHAR(200),
    uri                   TEXT,
    minio_key             TEXT,
    parsed_text           TEXT,
    parsed_metadata       JSONB         NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by           INTEGER,
    uploaded_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT channel_references_kind_chk CHECK (kind IN
        ('pdf','url','video','gdrive','notion','asset_pack','logo','lut','sfx','music'))
);
CREATE INDEX IF NOT EXISTS channel_references_channel_idx
    ON channel_references(channel_id, kind);

-- Persistent channel memory (viral patterns etc.)
CREATE TABLE IF NOT EXISTS channel_memory (
    id                    BIGSERIAL     PRIMARY KEY,
    channel_id            VARCHAR(20)   NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    memory_type           VARCHAR(40)   NOT NULL,
    content               JSONB         NOT NULL,
    embedding             vector(384),
    confidence            DECIMAL(4,3),
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    expires_at            TIMESTAMPTZ,
    CONSTRAINT channel_memory_type_chk CHECK (memory_type IN
        ('viral_pattern','failed_pattern','user_correction','preferred_prompt',
         'platform_optimization','review_decision','style_anchor'))
);
CREATE INDEX IF NOT EXISTS channel_memory_channel_idx
    ON channel_memory(channel_id, memory_type, created_at DESC);

-- Reusable channel presets (Faceless Educational, Commentary, etc.)
CREATE TABLE IF NOT EXISTS channel_presets (
    id                    BIGSERIAL     PRIMARY KEY,
    name                  VARCHAR(120)  UNIQUE NOT NULL,
    description           TEXT,
    payload               JSONB         NOT NULL,
    is_system             BOOLEAN       NOT NULL DEFAULT FALSE,
    created_by            INTEGER,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO channel_presets (name, description, is_system, payload) VALUES
    ('Faceless Educational', 'Voiceover + stock + kinetic text, info-heavy', TRUE,
     '{"content_style":"educational_narrative","narration_style":"calm_authoritative","music_style":"cinematic_minimal","pacing_style":"medium","content_type_tags":["faceless","educational","explainer"]}'::jsonb),
    ('Commentary',           'Reactive analysis with personality',          TRUE,
     '{"content_style":"commentary","narration_style":"opinionated","music_style":"upbeat_modern","pacing_style":"fast","content_type_tags":["commentary","analysis"]}'::jsonb),
    ('Storytelling',         'Long-form narrative, dramatic arc',            TRUE,
     '{"content_style":"storytelling","narration_style":"dramatic","music_style":"emotional_orchestral","pacing_style":"medium_slow","content_type_tags":["storytelling","narrative"]}'::jsonb),
    ('Shorts Hook-Fact-Payoff', 'Short-form 30-60s, viral-tuned',           TRUE,
     '{"content_style":"hook_fact_payoff","narration_style":"energetic","music_style":"trap_ambient","pacing_style":"very_fast","content_type_tags":["shorts","viral"]}'::jsonb)
ON CONFLICT (name) DO UPDATE SET payload = EXCLUDED.payload;

-- Wizard drafts (autosave)
CREATE TABLE IF NOT EXISTS channel_drafts (
    id                    BIGSERIAL     PRIMARY KEY,
    user_id               INTEGER,
    channel_id            VARCHAR(20),
    current_step          SMALLINT      NOT NULL DEFAULT 1,
    payload               JSONB         NOT NULL DEFAULT '{}'::jsonb,
    completeness_score    SMALLINT      NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS channel_drafts_user_idx
    ON channel_drafts(user_id, updated_at DESC);

-- ===== 202605090003_providers_v2.sql =====
-- 202605090003_providers_v2.sql
-- Phase 2 (S3): Provider/API management.
-- Secrets themselves live in Vault/Infisical; only references are in DB.

CREATE TABLE IF NOT EXISTS provider_categories (
    name        VARCHAR(40)   PRIMARY KEY,
    label       VARCHAR(120)  NOT NULL,
    kind        VARCHAR(20)   NOT NULL,  -- llm|tts|image|search|stock_footage|music|lut|sfx|storage
    description TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO provider_categories (name, label, kind, description) VALUES
    ('llm',           'LLM (general)',              'llm',           'Default LLM for general tasks'),
    ('llm.research',  'LLM — Research',             'llm',           'Research / fact-finding'),
    ('llm.script',    'LLM — Script',               'llm',           'Script generation / rewrites'),
    ('llm.factcheck', 'LLM — Fact-check',           'llm',           'Fact verification'),
    ('llm.qc',        'LLM — Quality Critique',     'llm',           'Output critique / scoring'),
    ('llm.vision',    'LLM — Vision',               'llm',           'Image analysis (CTR / scene)'),
    ('llm.ideation',  'LLM — Ideation',             'llm',           'Topic + hook ideation'),
    ('llm.hook',      'LLM — Hook',                 'llm',           'Hook writer'),
    ('llm.direction', 'LLM — Direction',            'llm',           'Visual direction generation'),
    ('llm.emotion',   'LLM — Emotion',              'llm',           'Emotion mapping for TTS'),
    ('tts',           'Text-to-Speech',             'tts',           'Voice synthesis'),
    ('image',         'Image generation',           'image',         'AI image generation'),
    ('search',        'Web search',                 'search',        'Real-time web search'),
    ('storage',       'Object storage',             'storage',       'Render artifacts + assets'),
    ('stock_footage', 'Stock footage',              'stock_footage', 'Stock video clips'),
    ('music',         'Background music',           'music',         'Production music'),
    ('lut',           'Color grading LUTs',         'lut',           'LUTs library'),
    ('sfx',           'Sound effects',              'sfx',           'SFX library')
ON CONFLICT (name) DO UPDATE SET label = EXCLUDED.label, kind = EXCLUDED.kind;

CREATE TABLE IF NOT EXISTS provider_credentials (
    id              BIGSERIAL     PRIMARY KEY,
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    provider_name   VARCHAR(60)   NOT NULL,    -- e.g. 'openai','elevenlabs','pexels'
    label           VARCHAR(120)  NOT NULL,    -- user-friendly name ("Personal OpenAI key")
    vault_path      TEXT          NOT NULL,    -- e.g. 'kv/data/providers/llm/openai/abc123'
    extra_config    JSONB         NOT NULL DEFAULT '{}'::jsonb,  -- non-secret config
    enabled         BOOLEAN       NOT NULL DEFAULT TRUE,
    rotation_due_at TIMESTAMPTZ,
    last_health_ok  BOOLEAN,
    last_health_at  TIMESTAMPTZ,
    last_latency_ms INTEGER,
    created_by      INTEGER,
    rotated_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (category, label)
);
CREATE INDEX IF NOT EXISTS provider_credentials_cat_idx
    ON provider_credentials(category, enabled);

CREATE TABLE IF NOT EXISTS provider_priority_chains (
    id                BIGSERIAL    PRIMARY KEY,
    category          VARCHAR(40)  NOT NULL REFERENCES provider_categories(name),
    position          SMALLINT     NOT NULL,
    credential_id     BIGINT       NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    fallback_strategy VARCHAR(20)  NOT NULL DEFAULT 'on_error',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (category, position),
    CONSTRAINT chain_strategy_chk CHECK (fallback_strategy IN
        ('on_error','on_rate_limit','on_timeout','always','manual'))
);
CREATE INDEX IF NOT EXISTS provider_chains_cat_idx
    ON provider_priority_chains(category, position);

CREATE TABLE IF NOT EXISTS provider_health_log (
    id            BIGSERIAL    PRIMARY KEY,
    credential_id BIGINT       NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    ok            BOOLEAN      NOT NULL,
    latency_ms    INTEGER,
    error         TEXT,
    checked_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS provider_health_credential_idx
    ON provider_health_log(credential_id, checked_at DESC);

-- ===== 202605090004_content_review.sql =====
-- 202605090004_content_review.sql
-- Phase 3 (S2 + S5): Generated Content browse + Manual Review.

-- Additive columns on videos
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS review_state         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS review_assigned_to   INTEGER,
    ADD COLUMN IF NOT EXISTS review_notes_count   INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS authenticity_score   DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS uniqueness_score     DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS title_embedding      vector(384),
    ADD COLUMN IF NOT EXISTS published_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS scheduled_at         TIMESTAMPTZ;

-- Generated week bucket. Postgres GENERATED stored cols can't reference
-- mutable funcs; date_trunc with constant timezone is immutable in pg15+.
-- Use a regular column + trigger for portability.
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS week_bucket DATE;

CREATE OR REPLACE FUNCTION videos_set_week_bucket() RETURNS TRIGGER AS $$
BEGIN
    NEW.week_bucket := date_trunc('week', COALESCE(NEW.created_at, NOW()))::date;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS videos_week_bucket_trg ON videos;
CREATE TRIGGER videos_week_bucket_trg
    BEFORE INSERT OR UPDATE OF created_at ON videos
    FOR EACH ROW EXECUTE FUNCTION videos_set_week_bucket();

-- Backfill existing rows
UPDATE videos
   SET week_bucket = date_trunc('week', created_at)::date
 WHERE week_bucket IS NULL;

CREATE INDEX IF NOT EXISTS videos_channel_week_idx
    ON videos(channel_id, week_bucket DESC);
CREATE INDEX IF NOT EXISTS videos_channel_created_idx
    ON videos(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS videos_review_state_idx
    ON videos(review_state) WHERE review_state IS NOT NULL;

-- Review sessions
CREATE TABLE IF NOT EXISTS review_sessions (
    id            BIGSERIAL     PRIMARY KEY,
    video_id      VARCHAR(50)   NOT NULL,  -- videos.content_id
    channel_id    VARCHAR(20)   NOT NULL,
    state         VARCHAR(20)   NOT NULL DEFAULT 'pending',
    opened_by     INTEGER,
    opened_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    decided_by    INTEGER,
    decided_at    TIMESTAMPTZ,
    summary       TEXT,
    expires_at    TIMESTAMPTZ,
    CONSTRAINT review_sessions_state_chk CHECK (state IN
        ('pending','approved','needs_edits','rejected','regenerating','timed_out'))
);
CREATE INDEX IF NOT EXISTS review_sessions_video_idx
    ON review_sessions(video_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS review_sessions_state_idx
    ON review_sessions(state, opened_at DESC) WHERE state = 'pending';

CREATE TABLE IF NOT EXISTS review_comments (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  BIGINT       NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    artifact    VARCHAR(20)  NOT NULL,
    anchor      JSONB,
    author_id   INTEGER,
    body        TEXT         NOT NULL,
    parent_id   BIGINT       REFERENCES review_comments(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT review_comments_artifact_chk CHECK (artifact IN
        ('script','thumbnail','title','description','tags','voice','timeline','seo','general'))
);
CREATE INDEX IF NOT EXISTS review_comments_session_idx
    ON review_comments(session_id, created_at);

-- Script & thumbnail versioning
CREATE TABLE IF NOT EXISTS script_versions (
    id              BIGSERIAL    PRIMARY KEY,
    video_id        VARCHAR(50)  NOT NULL,
    version         SMALLINT     NOT NULL,
    source          VARCHAR(20)  NOT NULL,
    content         JSONB        NOT NULL,
    diff_summary    TEXT,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, version),
    CONSTRAINT script_versions_source_chk CHECK (source IN
        ('ai_initial','ai_section','ai_full','human','tone_change','shorten','expand','restore'))
);
CREATE INDEX IF NOT EXISTS script_versions_video_idx
    ON script_versions(video_id, version DESC);

CREATE TABLE IF NOT EXISTS thumbnail_versions (
    id            BIGSERIAL    PRIMARY KEY,
    video_id      VARCHAR(50)  NOT NULL,
    version       SMALLINT     NOT NULL,
    source        VARCHAR(20)  NOT NULL,    -- ai|human
    minio_key     TEXT         NOT NULL,
    prompt        TEXT,
    ctr_pred      DECIMAL(5,4),
    composition   JSONB,
    created_by    INTEGER,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, version)
);
CREATE INDEX IF NOT EXISTS thumbnail_versions_video_idx
    ON thumbnail_versions(video_id, version DESC);

-- Postgres FTS for content search
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS title_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title,'') || ' ' || coalesce(topic,'') || ' ' || coalesce(selected_hook,'')
        )
    ) STORED;
CREATE INDEX IF NOT EXISTS videos_title_tsv_idx ON videos USING gin(title_tsv);

-- ===== 202605090005_auth_notifications.sql =====
-- 202605090005_auth_notifications.sql
-- Phase 4 (S7 + S4 + S8): Real auth + notification center.

-- Users
CREATE TABLE IF NOT EXISTS users (
    id                BIGSERIAL    PRIMARY KEY,
    email             VARCHAR(255) UNIQUE NOT NULL,
    display_name      VARCHAR(120),
    password_hash     TEXT,
    role              VARCHAR(20)  NOT NULL DEFAULT 'viewer',
    mfa_secret        TEXT,
    mfa_enabled       BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verified    BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verify_token TEXT,
    oauth_providers   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    last_login_at     TIMESTAMPTZ,
    disabled          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT users_role_chk CHECK (role IN ('owner','admin','editor','reviewer','viewer'))
);
CREATE INDEX IF NOT EXISTS users_email_idx ON users(lower(email));

CREATE TABLE IF NOT EXISTS sessions (
    id                  BIGSERIAL    PRIMARY KEY,
    user_id             BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  TEXT         NOT NULL UNIQUE,
    device              TEXT,
    ip                  VARCHAR(45),
    user_agent          TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ  NOT NULL,
    revoked_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS password_resets (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT         NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ  NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id            BIGSERIAL    PRIMARY KEY,
    event_type    VARCHAR(80)  NOT NULL,
    severity      VARCHAR(20)  NOT NULL DEFAULT 'info',
    title         TEXT         NOT NULL,
    body          TEXT,
    payload       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    channel_id    VARCHAR(20),
    video_id      VARCHAR(100),
    dedupe_key    VARCHAR(120),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    read_by       BIGINT[]     NOT NULL DEFAULT '{}',
    CONSTRAINT notifications_severity_chk CHECK (severity IN ('info','warn','error','critical'))
);
CREATE INDEX IF NOT EXISTS notifications_recent_idx ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS notifications_dedupe_idx ON notifications(dedupe_key, created_at DESC)
    WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS notifications_event_idx ON notifications(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_routes (
    id              BIGSERIAL    PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    event_pattern   VARCHAR(120) NOT NULL,  -- supports '*' wildcards
    severity_min    VARCHAR(20)  NOT NULL DEFAULT 'info',
    channels        TEXT[]       NOT NULL,  -- ['slack','email','browser','webhook']
    filter          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    config          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id              BIGSERIAL    PRIMARY KEY,
    notification_id BIGINT       NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    route_id        BIGINT       REFERENCES notification_routes(id) ON DELETE SET NULL,
    channel         VARCHAR(40)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'queued',
    attempts        SMALLINT     NOT NULL DEFAULT 0,
    response        JSONB,
    error           TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT deliveries_status_chk CHECK (status IN ('queued','sent','failed','dropped'))
);
CREATE INDEX IF NOT EXISTS deliveries_notification_idx
    ON notification_deliveries(notification_id);
CREATE INDEX IF NOT EXISTS deliveries_status_idx
    ON notification_deliveries(status, created_at DESC);

-- Default routes (disabled until user configures Slack/email)
INSERT INTO notification_routes (name, event_pattern, severity_min, channels, enabled) VALUES
    ('Critical to Slack',     '*',                 'critical', ARRAY['slack'],   FALSE),
    ('Errors to Slack',       'pipeline.*',        'error',    ARRAY['slack'],   FALSE),
    ('Review pending',        'review.pending',    'info',     ARRAY['browser'], TRUE),
    ('Job complete',          'video.complete',    'info',     ARRAY['browser'], TRUE),
    ('Provider failure',      'provider.failed',   'warn',     ARRAY['slack'],   FALSE)
ON CONFLICT DO NOTHING;

-- ===== 202605100001_channels_publish_cadence.sql =====
-- 202605100001_channels_publish_cadence.sql
-- Adds the publish_cadence column referenced by the v2 channels list query.
-- The legacy table has `posting_frequency` (e.g. 'daily') which we copy over
-- as a default so existing channels don't show NULL in the dashboard.

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS publish_cadence VARCHAR(40);

UPDATE channels
   SET publish_cadence = posting_frequency
 WHERE publish_cadence IS NULL
   AND posting_frequency IS NOT NULL;

-- ===== 202605110001_tenancy_hierarchy.sql =====
-- 202605110001_tenancy_hierarchy.sql
-- Wave 1: Workspace → Brand → Channel → Series → Campaign → Project hierarchy.
-- All additive. Existing channels are backfilled to a default workspace + brand.

-- pgvector extension (already added by research service migration; safe to re-run)
CREATE EXTENSION IF NOT EXISTS vector;

-- Workspaces (tenant root, billing boundary)
CREATE TABLE IF NOT EXISTS workspaces (
    id                  BIGSERIAL       PRIMARY KEY,
    name                VARCHAR(120)    NOT NULL,
    slug                VARCHAR(80)     UNIQUE NOT NULL,
    plan                VARCHAR(30)     NOT NULL DEFAULT 'starter',
    owner_user_id       BIGINT,
    billing_email       VARCHAR(255),
    monthly_budget_usd  DECIMAL(10,2)   NOT NULL DEFAULT 100.00,
    timezone            VARCHAR(60)     NOT NULL DEFAULT 'UTC',
    logo_url            TEXT,
    settings            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT workspaces_plan_chk CHECK (plan IN ('starter','growth','scale','enterprise'))
);

INSERT INTO workspaces (id, name, slug, plan)
VALUES (1, 'Default Workspace', 'default', 'starter')
ON CONFLICT (slug) DO NOTHING;

-- Brands (visual identity / legal entity under workspace)
CREATE TABLE IF NOT EXISTS brands (
    id              BIGSERIAL       PRIMARY KEY,
    workspace_id    BIGINT          NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name            VARCHAR(120)    NOT NULL,
    slug            VARCHAR(80)     NOT NULL,
    description     TEXT,
    legal_name      VARCHAR(200),
    website         TEXT,
    primary_color   VARCHAR(7),
    secondary_color VARCHAR(7),
    logo_url        TEXT,
    voice_summary   TEXT,
    settings        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_by      BIGINT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, slug)
);
CREATE INDEX IF NOT EXISTS brands_workspace_idx ON brands(workspace_id);

INSERT INTO brands (id, workspace_id, name, slug)
VALUES (1, 1, 'Default Brand', 'default')
ON CONFLICT (workspace_id, slug) DO NOTHING;

-- Add brand_id + workspace_id to channels
ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS brand_id     BIGINT REFERENCES brands(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) ON DELETE SET NULL;

UPDATE channels SET brand_id = 1, workspace_id = 1 WHERE brand_id IS NULL;

CREATE INDEX IF NOT EXISTS channels_brand_idx     ON channels(brand_id);
CREATE INDEX IF NOT EXISTS channels_workspace_idx ON channels(workspace_id);

-- Series (recurring show/format under a channel)
CREATE TABLE IF NOT EXISTS series (
    id                  BIGSERIAL       PRIMARY KEY,
    channel_id          VARCHAR(20)     NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    name                VARCHAR(120)    NOT NULL,
    description         TEXT,
    format              VARCHAR(60),
    target_duration_s   INTEGER,
    cadence             VARCHAR(40),
    thumbnail_style     VARCHAR(80),
    settings            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_by          BIGINT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS series_channel_idx ON series(channel_id, is_active);

-- Campaigns (time-bound theme under a brand)
CREATE TABLE IF NOT EXISTS campaigns (
    id              BIGSERIAL       PRIMARY KEY,
    brand_id        BIGINT          NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name            VARCHAR(120)    NOT NULL,
    description     TEXT,
    theme           TEXT,
    start_at        TIMESTAMPTZ,
    end_at          TIMESTAMPTZ,
    kpi_targets     JSONB           NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(20)     NOT NULL DEFAULT 'draft',
    created_by      BIGINT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT campaigns_status_chk CHECK (status IN
        ('draft','active','paused','completed','archived'))
);
CREATE INDEX IF NOT EXISTS campaigns_brand_idx ON campaigns(brand_id, status);

-- Projects (one video idea / brief; supports branching)
CREATE TABLE IF NOT EXISTS projects (
    id                  BIGSERIAL       PRIMARY KEY,
    channel_id          VARCHAR(20)     NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    series_id           BIGINT          REFERENCES series(id) ON DELETE SET NULL,
    campaign_id         BIGINT          REFERENCES campaigns(id) ON DELETE SET NULL,
    parent_project_id   BIGINT          REFERENCES projects(id) ON DELETE SET NULL,
    branch_label        VARCHAR(80),
    title               VARCHAR(255)    NOT NULL,
    brief               TEXT,
    status              VARCHAR(30)     NOT NULL DEFAULT 'idea',
    priority            SMALLINT        NOT NULL DEFAULT 5,
    target_publish_at   TIMESTAMPTZ,
    tags                TEXT[]          NOT NULL DEFAULT '{}',
    estimated_cost_usd  DECIMAL(10,4),
    actual_cost_usd     DECIMAL(10,4),
    settings            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_by          BIGINT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT projects_status_chk CHECK (status IN (
        'idea','scripting','storyboard','assets','voice','render',
        'review','scheduled','published','archived'
    ))
);
CREATE INDEX IF NOT EXISTS projects_channel_status_idx  ON projects(channel_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS projects_series_idx          ON projects(series_id)          WHERE series_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS projects_campaign_idx        ON projects(campaign_id)        WHERE campaign_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS projects_parent_idx          ON projects(parent_project_id)  WHERE parent_project_id IS NOT NULL;

-- Link videos → projects
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS videos_project_idx ON videos(project_id) WHERE project_id IS NOT NULL;

-- ── Entity settings (key/value per scope, with lock/inherit) ─
CREATE TABLE IF NOT EXISTS entity_settings (
    id          BIGSERIAL       PRIMARY KEY,
    scope       VARCHAR(30)     NOT NULL,
    scope_id    VARCHAR(40)     NOT NULL,
    key         VARCHAR(120)    NOT NULL,
    value       JSONB,
    locked      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (scope, scope_id, key),
    CONSTRAINT entity_settings_scope_chk CHECK (scope IN
        ('system','workspace','brand','channel','series','campaign','project'))
);
CREATE INDEX IF NOT EXISTS entity_settings_scope_idx ON entity_settings(scope, scope_id);

-- ── Brand kits (first-class bundle: logo, palette, fonts, etc.) ─
CREATE TABLE IF NOT EXISTS brand_kits (
    id              BIGSERIAL       PRIMARY KEY,
    brand_id        BIGINT          NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name            VARCHAR(120)    NOT NULL DEFAULT 'Default Kit',
    version         SMALLINT        NOT NULL DEFAULT 1,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    logo_url        TEXT,
    palette         JSONB           NOT NULL DEFAULT '[]'::jsonb,
    font_primary    VARCHAR(120),
    font_secondary  VARCHAR(120),
    motion_preset   VARCHAR(80),
    voice_preset    VARCHAR(80),
    lut_key         TEXT,
    intro_key       TEXT,
    outro_key       TEXT,
    extra           JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS brand_kits_brand_idx ON brand_kits(brand_id, is_active);

-- ===== 202605110002_membership_rbac.sql =====
-- 202605110002_membership_rbac.sql
-- Wave 1: Multi-user RBAC with scoped role bindings.
-- Depends on: users table (202605090005), workspaces + brands (202605110001).

-- Workspace memberships
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id    BIGINT          NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         BIGINT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(30)     NOT NULL DEFAULT 'viewer',
    invited_by      BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    joined_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id),
    CONSTRAINT wm_role_chk CHECK (role IN
        ('owner','admin','producer','editor','reviewer','analyst','viewer'))
);
CREATE INDEX IF NOT EXISTS workspace_members_user_idx ON workspace_members(user_id);

-- Backfill existing users into the default workspace
INSERT INTO workspace_members (workspace_id, user_id, role)
SELECT 1, id,
       CASE WHEN role IN ('owner','admin','editor','reviewer','viewer') THEN role ELSE 'viewer' END
FROM users
ON CONFLICT (workspace_id, user_id) DO NOTHING;

-- Fine-grained role bindings (scope-level)
CREATE TABLE IF NOT EXISTS role_bindings (
    id          BIGSERIAL       PRIMARY KEY,
    user_id     BIGINT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope       VARCHAR(30)     NOT NULL,
    scope_id    VARCHAR(40)     NOT NULL,
    role        VARCHAR(30)     NOT NULL,
    granted_by  BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, scope, scope_id),
    CONSTRAINT rb_scope_chk CHECK (scope IN
        ('global','workspace','brand','channel')),
    CONSTRAINT rb_role_chk CHECK (role IN
        ('owner','admin','producer','editor','reviewer','analyst','viewer','external_reviewer'))
);
CREATE INDEX IF NOT EXISTS role_bindings_user_idx  ON role_bindings(user_id, scope);
CREATE INDEX IF NOT EXISTS role_bindings_scope_idx ON role_bindings(scope, scope_id);

-- Workspace invitations
CREATE TABLE IF NOT EXISTS workspace_invitations (
    id              BIGSERIAL       PRIMARY KEY,
    workspace_id    BIGINT          NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email           VARCHAR(255)    NOT NULL,
    role            VARCHAR(30)     NOT NULL DEFAULT 'viewer',
    token_hash      TEXT            NOT NULL UNIQUE,
    invited_by      BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    accepted_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS workspace_invitations_ws_idx ON workspace_invitations(workspace_id, accepted_at);

-- Permission check helper view
-- Returns the effective role for (user, scope, scope_id).
-- Resolution: global → workspace → brand → channel (most specific wins).
-- Used by application code via SELECT * FROM effective_role WHERE ...
CREATE OR REPLACE VIEW effective_roles AS
SELECT
    rb.user_id,
    rb.scope,
    rb.scope_id,
    rb.role,
    CASE rb.scope
        WHEN 'global'    THEN 1
        WHEN 'workspace' THEN 2
        WHEN 'brand'     THEN 3
        WHEN 'channel'   THEN 4
    END AS specificity
FROM role_bindings rb
WHERE (rb.expires_at IS NULL OR rb.expires_at > NOW());

-- Feature flags for RBAC enforcement
INSERT INTO feature_flags (key, enabled, description) VALUES
    ('auth.rbac.enabled',        FALSE, 'Enforce fine-grained RBAC; when disabled, all authenticated users are treated as owner'),
    ('auth.invitations.enabled', FALSE, 'Enable workspace invitation flow')
ON CONFLICT (key) DO NOTHING;

-- ===== 202605110003_assets_dam.sql =====
-- Wave 3: DAM — scoped asset store, versions, collections
-- Additive only; does not touch existing asset_library / brand_assets tables.

-- dam_assets
CREATE TABLE IF NOT EXISTS dam_assets (
    id            BIGSERIAL PRIMARY KEY,
    scope         VARCHAR(20)   NOT NULL DEFAULT 'workspace'
                  CHECK (scope IN ('system','workspace','brand','channel','project')),
    scope_id      VARCHAR(100),                     -- NULL means "applies to all" for system scope
    kind          VARCHAR(30)   NOT NULL
                  CHECK (kind IN ('image','video','audio','font','lut','template','document','other')),
    display_name  VARCHAR(500)  NOT NULL,
    mime_type     VARCHAR(100),
    bytes         BIGINT,
    content_hash  VARCHAR(64),                       -- SHA-256 for exact-dedup
    storage_key   VARCHAR(1000),                     -- MinIO object key
    thumbnail_key VARCHAR(1000),                     -- MinIO key for poster/thumb
    origin        VARCHAR(30)   NOT NULL DEFAULT 'uploaded'
                  CHECK (origin IN ('uploaded','generated','stock','imported')),
    license       VARCHAR(100),
    license_url   TEXT,
    expires_at    TIMESTAMPTZ,
    tags          TEXT[]        NOT NULL DEFAULT '{}',
    ai_tags       JSONB         NOT NULL DEFAULT '{}', -- {tag: confidence}
    metadata      JSONB         NOT NULL DEFAULT '{}', -- codec, width, height, duration_ms, bitrate…
    created_by    VARCHAR(200),
    deleted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dam_assets_scope
    ON dam_assets (scope, scope_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_kind
    ON dam_assets (kind) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_hash
    ON dam_assets (content_hash) WHERE content_hash IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_tags
    ON dam_assets USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_dam_assets_created
    ON dam_assets (created_at DESC) WHERE deleted_at IS NULL;
-- Full-text search over display_name
CREATE INDEX IF NOT EXISTS idx_dam_assets_fts
    ON dam_assets USING GIN (to_tsvector('english', display_name));

-- dam_asset_versions
CREATE TABLE IF NOT EXISTS dam_asset_versions (
    id           BIGSERIAL PRIMARY KEY,
    asset_id     BIGINT        NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    version_no   SMALLINT      NOT NULL,
    storage_key  VARCHAR(1000),
    bytes        BIGINT,
    content_hash VARCHAR(64),
    transform    JSONB         NOT NULL DEFAULT '{}', -- crop, resize, etc. applied
    note         TEXT,
    created_by   VARCHAR(200),
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (asset_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_dam_versions_asset ON dam_asset_versions (asset_id);

-- dam_collections
CREATE TABLE IF NOT EXISTS dam_collections (
    id          BIGSERIAL PRIMARY KEY,
    scope       VARCHAR(20)   NOT NULL DEFAULT 'workspace',
    scope_id    VARCHAR(100),
    name        VARCHAR(200)  NOT NULL,
    description TEXT,
    kind        VARCHAR(10)   NOT NULL DEFAULT 'manual'
                CHECK (kind IN ('manual','smart')),
    query       JSONB         NOT NULL DEFAULT '{}',    -- smart collection DSL
    asset_ids   BIGINT[]      NOT NULL DEFAULT '{}',    -- manual member list
    cover_asset_id BIGINT REFERENCES dam_assets(id) ON DELETE SET NULL,
    owner_id    VARCHAR(200),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dam_collections_scope
    ON dam_collections (scope, scope_id);

-- dam_brand_kits
CREATE TABLE IF NOT EXISTS dam_brand_kits (
    id              BIGSERIAL PRIMARY KEY,
    scope           VARCHAR(20)  NOT NULL DEFAULT 'brand',
    scope_id        VARCHAR(100),
    name            VARCHAR(200) NOT NULL,
    version_no      SMALLINT     NOT NULL DEFAULT 1,
    logo_asset_ids  BIGINT[]     NOT NULL DEFAULT '{}',
    palette         JSONB        NOT NULL DEFAULT '{}',  -- {primary, secondary, accent, bg}
    font_asset_ids  BIGINT[]     NOT NULL DEFAULT '{}',
    lut_asset_id    BIGINT       REFERENCES dam_assets(id) ON DELETE SET NULL,
    intro_asset_id  BIGINT       REFERENCES dam_assets(id) ON DELETE SET NULL,
    outro_asset_id  BIGINT       REFERENCES dam_assets(id) ON DELETE SET NULL,
    voice_sample_id BIGINT       REFERENCES dam_assets(id) ON DELETE SET NULL,
    motion_presets  JSONB        NOT NULL DEFAULT '{}',
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dam_brand_kits_scope
    ON dam_brand_kits (scope, scope_id);

-- helper trigger: updated_at
CREATE OR REPLACE FUNCTION dam_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_dam_assets_updated_at')
  THEN CREATE TRIGGER trg_dam_assets_updated_at
       BEFORE UPDATE ON dam_assets
       FOR EACH ROW EXECUTE FUNCTION dam_set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_dam_collections_updated_at')
  THEN CREATE TRIGGER trg_dam_collections_updated_at
       BEFORE UPDATE ON dam_collections
       FOR EACH ROW EXECUTE FUNCTION dam_set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_dam_brand_kits_updated_at')
  THEN CREATE TRIGGER trg_dam_brand_kits_updated_at
       BEFORE UPDATE ON dam_brand_kits
       FOR EACH ROW EXECUTE FUNCTION dam_set_updated_at();
  END IF;
END $$;

-- ===== 202605110004_pgvector_embeddings.sql =====
-- Wave 3: pgvector — semantic search embeddings for DAM assets
-- Requires pgvector extension (already enabled via research service migration,
-- but CREATE EXTENSION IF NOT EXISTS is idempotent).

CREATE EXTENSION IF NOT EXISTS vector;

-- dam_asset_embeddings
-- Stores CLIP/SBERT/Whisper embeddings per asset per model+modality.
-- Dimension 768 covers both CLIP-L/14 and all-MiniLM-L6-v2 (padded if smaller).
CREATE TABLE IF NOT EXISTS dam_asset_embeddings (
    asset_id    BIGINT        NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    model       VARCHAR(100)  NOT NULL,  -- e.g. clip-vit-l-14, all-minilm-l6-v2
    modality    VARCHAR(20)   NOT NULL DEFAULT 'visual'
                CHECK (modality IN ('visual','text','audio')),
    embedding   vector(768),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_id, model, modality)
);

-- IVFFlat index for ANN cosine similarity (100 lists ≈ good for up to ~500k rows)
CREATE INDEX IF NOT EXISTS idx_dam_embeddings_ivfflat
    ON dam_asset_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ===== 202605110005_provider_routing.sql =====
-- 202605110005_provider_routing.sql
-- Wave 2: provider_routes, provider_quotas, provider_marketplace_catalog, provider_sandbox_runs
-- Additive only — no destructive changes to existing tables.

-- Provider marketplace catalog
-- Static registry of all known providers (connected or not).
CREATE TABLE IF NOT EXISTS provider_marketplace_catalog (
    id              BIGSERIAL     PRIMARY KEY,
    provider_key    VARCHAR(60)   NOT NULL UNIQUE,  -- e.g. 'openai', 'elevenlabs', 'pexels'
    display_name    VARCHAR(120)  NOT NULL,
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    description     TEXT,
    logo_url        TEXT,
    website_url     TEXT,
    mode            VARCHAR(20)   NOT NULL DEFAULT 'byok',  -- byok|system|marketplace|internal
    capabilities    TEXT[]        NOT NULL DEFAULT '{}',     -- e.g. ['text-gen','vision','function-call']
    pricing_notes   TEXT,
    cost_unit       VARCHAR(60),   -- e.g. '$0.002 / 1K tokens'
    regions         TEXT[]        NOT NULL DEFAULT '{}',
    has_free_tier   BOOLEAN       NOT NULL DEFAULT FALSE,
    featured        BOOLEAN       NOT NULL DEFAULT FALSE,
    sort_order      SMALLINT      NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS pmcat_category_idx ON provider_marketplace_catalog(category);
CREATE INDEX IF NOT EXISTS pmcat_mode_idx ON provider_marketplace_catalog(mode);

-- Seed the catalog with known providers
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    -- LLM
    ('openai',        'OpenAI (GPT-4o)',       'llm',   'State-of-the-art general purpose LLM with vision.',         'byok',     ARRAY['text-gen','function-call','vision','json-mode'], '$0.002/1K tok',  false, true,  10),
    ('anthropic',     'Anthropic (Claude)',    'llm',   'Constitutional AI — strong reasoning, 200K context.',       'byok',     ARRAY['text-gen','function-call','vision'],              '$0.003/1K tok',  false, true,  20),
    ('gemini',        'Google Gemini',         'llm',   'Multimodal flagship model from Google DeepMind.',           'byok',     ARRAY['text-gen','vision','function-call'],              '$0.001/1K tok',  false, false, 30),
    ('groq',          'Groq (Llama-3)',        'llm',   'Ultra-fast inference on open-source models.',               'byok',     ARRAY['text-gen'],                                      '$0.0001/1K tok', true,  false, 40),
    ('ollama',        'Ollama (local)',        'llm',   'Run open-source models locally — zero marginal cost.',      'internal', ARRAY['text-gen'],                                      '$0.00 (local)',  true,  false, 50),
    -- TTS
    ('fishaudio',     'Fish Audio',            'tts',   'Expressive PAYG TTS with emotion parameter control.',       'byok',     ARRAY['tts-standard','tts-emotion','tts-clone'],        '$0.001/char',    false, true,  10),
    ('elevenlabs',    'ElevenLabs',            'tts',   'Industry-leading TTS with voice cloning and emotion.',      'byok',     ARRAY['tts-standard','tts-emotion','tts-clone'],        '$0.0003/char',   true,  true,  20),
    ('edge_tts',      'Edge TTS (free)',       'tts',   'Microsoft Edge TTS — free tier, good quality.',             'system',   ARRAY['tts-standard'],                                  'Free',           true,  false, 30),
    -- Image
    ('openai_dalle',  'DALL-E 3',              'image', 'High-quality image generation from OpenAI.',               'byok',     ARRAY['image-gen','image-edit'],                         '$0.04/image',    false, true,  10),
    ('stability',     'Stability AI',          'image', 'Stable Diffusion API — flexible and low cost.',             'byok',     ARRAY['image-gen','image-edit','upscale'],               '$0.002/image',   false, false, 20),
    ('fal_ai',        'fal.ai',                'image', 'Fast image models including Flux and SDXL.',                'byok',     ARRAY['image-gen'],                                     '$0.003/image',   true,  false, 30),
    -- Search
    ('perplexity',    'Perplexity',            'search','Real-time web search with cited sources.',                  'byok',     ARRAY['web-search','news-search'],                      '$5/1K req',      false, true,  10),
    ('serper',        'Serper',                'search','Google SERP API — fast, cheap, accurate.',                  'byok',     ARRAY['web-search','news-search','image-search'],        '$0.001/req',     true,  true,  20),
    ('tavily',        'Tavily',                'search','AI-optimized search API with structured output.',           'byok',     ARRAY['web-search'],                                    '$0.002/req',     true,  false, 30),
    -- Stock footage
    ('pexels',        'Pexels',                'stock_footage', 'Free stock photos and videos.',                     'byok',     ARRAY['stock-video','stock-image'],                     'Free',           true,  true,  10),
    ('pixabay',       'Pixabay',               'stock_footage', 'Free-to-use media library.',                        'byok',     ARRAY['stock-video','stock-image'],                     'Free',           true,  false, 20),
    ('envato',        'Envato Elements',       'stock_footage', 'Premium stock footage library.',                    'byok',     ARRAY['stock-video','stock-image','music'],              '$16.50/mo',      false, false, 30)
ON CONFLICT (provider_key) DO UPDATE
    SET display_name  = EXCLUDED.display_name,
        capabilities  = EXCLUDED.capabilities,
        cost_unit     = EXCLUDED.cost_unit,
        featured      = EXCLUDED.featured;


-- Provider routing policies (scope-aware)
-- Each row says: for capability X at scope Y, route using policy Z with these constraints.
CREATE TABLE IF NOT EXISTS provider_routes (
    id              BIGSERIAL     PRIMARY KEY,
    scope           VARCHAR(20)   NOT NULL DEFAULT 'workspace',  -- system|workspace|brand|channel|project
    scope_id        VARCHAR(120),  -- NULL = system-wide
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    policy          VARCHAR(20)   NOT NULL DEFAULT 'balanced',   -- cheapest|fastest|highest_quality|balanced|custom
    custom_rules    JSONB         NOT NULL DEFAULT '{}'::jsonb,  -- JSON-Logic expression (for 'custom' policy)
    primary_credential_id  BIGINT REFERENCES provider_credentials(id) ON DELETE SET NULL,
    fallback_chain  BIGINT[]      NOT NULL DEFAULT '{}',         -- ordered credential_ids
    enabled         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT route_policy_chk CHECK (policy IN ('cheapest','fastest','highest_quality','balanced','custom')),
    CONSTRAINT route_scope_chk  CHECK (scope   IN ('system','workspace','brand','channel','project')),
    UNIQUE (scope, scope_id, category)
);
CREATE INDEX IF NOT EXISTS provider_routes_scope_idx ON provider_routes(scope, scope_id);
CREATE INDEX IF NOT EXISTS provider_routes_category_idx ON provider_routes(category);


-- Provider quotas
-- Monthly spend caps per scope. On INSERT/UPDATE the period resets each calendar month.
CREATE TABLE IF NOT EXISTS provider_quotas (
    id              BIGSERIAL     PRIMARY KEY,
    scope           VARCHAR(20)   NOT NULL DEFAULT 'workspace',
    scope_id        VARCHAR(120),
    category        VARCHAR(40)   REFERENCES provider_categories(name),  -- NULL = all categories
    monthly_cap_usd NUMERIC(10,4) NOT NULL DEFAULT 50.0,
    current_spend   NUMERIC(10,4) NOT NULL DEFAULT 0.0,
    period_start    DATE          NOT NULL DEFAULT DATE_TRUNC('month', NOW()),
    alert_pct       SMALLINT      NOT NULL DEFAULT 80,  -- send alert when spend > alert_pct% of cap
    hard_limit      BOOLEAN       NOT NULL DEFAULT FALSE, -- if TRUE: reject requests when capped
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT quota_scope_chk CHECK (scope IN ('system','workspace','brand','channel','project')),
    UNIQUE (scope, scope_id, category)
);

-- Sandbox run log
-- Stores test inference outputs for the sandbox runner UI.
CREATE TABLE IF NOT EXISTS provider_sandbox_runs (
    id              BIGSERIAL     PRIMARY KEY,
    credential_id   BIGINT        NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    run_by          INTEGER,
    capability      VARCHAR(40)   NOT NULL,  -- 'text-gen','tts-standard','image-gen'
    input_payload   JSONB         NOT NULL DEFAULT '{}'::jsonb,
    output_payload  JSONB         NOT NULL DEFAULT '{}'::jsonb,
    ok              BOOLEAN       NOT NULL DEFAULT FALSE,
    latency_ms      INTEGER,
    cost_usd        NUMERIC(10,6),
    error           TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS psandbox_credential_idx ON provider_sandbox_runs(credential_id, created_at DESC);
CREATE INDEX IF NOT EXISTS psandbox_run_by_idx ON provider_sandbox_runs(run_by, created_at DESC);

-- ===== 202605110006_review_collab.sql =====
-- Migration 006: Review Collaboration (additive)
-- Adds frame-accurate comments, annotations, approvals, and the content
-- generation trigger queue. Leaves `review_sessions` and `review_comments`
-- untouched — those are owned by migration 004 and the live BFF
-- (`src/services/dashboard/v2/review.py`) still uses that schema.
--
-- Safe to re-run (CREATE … IF NOT EXISTS + DO blocks).

-- Frame-accurate comments (new — supplements 004's review_comments)
CREATE TABLE IF NOT EXISTS frame_comments (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    author_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    timecode_s    NUMERIC(10,3),          -- seconds from start; NULL = general
    body          TEXT NOT NULL,
    resolved      BOOLEAN NOT NULL DEFAULT FALSE,
    parent_id     BIGINT REFERENCES frame_comments(id) ON DELETE SET NULL, -- threads
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_frame_comments_session  ON frame_comments(session_id);
CREATE INDEX IF NOT EXISTS idx_frame_comments_resolved ON frame_comments(session_id, resolved);

-- Annotations (visual overlays on thumbnail / frame)
CREATE TABLE IF NOT EXISTS review_annotations (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    author_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    timecode_s    NUMERIC(10,3),
    kind          TEXT NOT NULL DEFAULT 'rect'   -- rect | arrow | text | circle
                  CHECK (kind IN ('rect','arrow','text','circle')),
    coords        JSONB NOT NULL,                -- {x, y, w, h} or {x1,y1,x2,y2}
    label         TEXT,
    color         TEXT DEFAULT '#f97316',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_annotations_session ON review_annotations(session_id);

-- Approvals (per-reviewer decision)
CREATE TABLE IF NOT EXISTS review_approvals (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    reviewer_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('approved','rejected','needs_edits')),
    note          TEXT,
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, reviewer_id)
);
CREATE INDEX IF NOT EXISTS idx_approvals_session ON review_approvals(session_id);

-- Content generation queue (trigger tracking)
CREATE TABLE IF NOT EXISTS content_triggers (
    id            BIGSERIAL PRIMARY KEY,
    channel_id    TEXT NOT NULL,
    content_mode  TEXT NOT NULL DEFAULT 'long_form',
    topic_hint    TEXT,
    scheduled_for TIMESTAMPTZ,
    triggered_by  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','done','failed','cancelled')),
    content_id    TEXT,                          -- filled once workflow starts
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_triggers_channel ON content_triggers(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_triggers_status  ON content_triggers(status);

-- updated_at triggers (only for tables that own an updated_at column)
CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_frame_comments_upd') THEN
    CREATE TRIGGER trg_frame_comments_upd
      BEFORE UPDATE ON frame_comments
      FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_content_triggers_upd') THEN
    CREATE TRIGGER trg_content_triggers_upd
      BEFORE UPDATE ON content_triggers
      FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
  END IF;
END $$;

-- ===== 202605110008_transcoding_jobs.sql =====
-- Wave 3: Transcoding pipeline tables
-- media_jobs  — work queue entries for each pipeline step per asset
-- media_renditions — output artifacts produced by jobs

-- media_jobs
CREATE TABLE IF NOT EXISTS media_jobs (
    id           BIGSERIAL PRIMARY KEY,
    asset_id     BIGINT       NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    kind         VARCHAR(30)  NOT NULL
                 CHECK (kind IN (
                     'probe','transcode_hls','transcode_mp4',
                     'poster','waveform','embed',
                     'transcribe','autotag','safety_scan',
                     'perceptual_hash','dedup_cluster'
                 )),
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','running','done','failed','skipped')),
    priority     SMALLINT     NOT NULL DEFAULT 5,   -- lower = higher priority
    attempts     SMALLINT     NOT NULL DEFAULT 0,
    max_attempts SMALLINT     NOT NULL DEFAULT 3,
    worker_id    VARCHAR(100),                       -- hostname that claimed the job
    error        TEXT,
    result       JSONB        NOT NULL DEFAULT '{}',
    scheduled_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_media_jobs_pending
    ON media_jobs (priority, scheduled_at)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_media_jobs_asset
    ON media_jobs (asset_id, kind);
CREATE INDEX IF NOT EXISTS idx_media_jobs_status
    ON media_jobs (status, created_at DESC);

-- media_renditions
CREATE TABLE IF NOT EXISTS media_renditions (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT      NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    rendition_kind  VARCHAR(30) NOT NULL
                    CHECK (rendition_kind IN (
                        'proxy_hls','proxy_mp4','poster',
                        'waveform','thumbnail_strip','transcript','subtitle_srt'
                    )),
    storage_key     VARCHAR(1000),
    codec           VARCHAR(50),
    width           INT,
    height          INT,
    bitrate_kbps    INT,
    duration_ms     INT,
    bytes           BIGINT,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, rendition_kind)   -- one rendition per kind per asset (upsert-safe)
);

CREATE INDEX IF NOT EXISTS idx_media_renditions_asset
    ON media_renditions (asset_id, rendition_kind);

-- ===== 202605140001_providers_scope.sql =====
-- 202605140001_providers_scope.sql
-- Wave 4: Make provider chains scope-aware (workspace/channel) AND content-mode aware
-- (short/long_form), and let each credential pin a specific model.
--
-- Additive only. The legacy `provider_priority_chains` table is retained read-only
-- for one release; existing rows are mirrored into `provider_chains_v2` so the new
-- runtime resolves them as workspace+mode-agnostic chains.

-- 1. content_modes
CREATE TABLE IF NOT EXISTS content_modes (
    name        VARCHAR(40)   PRIMARY KEY,
    label       VARCHAR(120)  NOT NULL,
    description TEXT,
    sort_order  SMALLINT      NOT NULL DEFAULT 100,
    is_system   BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO content_modes (name, label, description, sort_order, is_system) VALUES
    ('short',     'Short-form', 'Shorts / Reels / TikTok-style ≤60s',  10, TRUE),
    ('long_form', 'Long-form',  'Standard YouTube ≥3min',              20, TRUE)
ON CONFLICT (name) DO UPDATE
   SET label       = EXCLUDED.label,
       description = EXCLUDED.description,
       sort_order  = EXCLUDED.sort_order,
       is_system   = EXCLUDED.is_system;

-- 2. provider_credentials extensions
-- Per-credential model pin (e.g. 'claude-sonnet-4-20250514', 'gpt-4o-mini',
-- ElevenLabs voice id, dall-e-3). NULL = use provider's default_model().
ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS model VARCHAR(120);

-- Explicit "always tried last" fallback flag. At most one per category.
ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS is_default_fallback BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS provider_credentials_one_default_per_cat
    ON provider_credentials(category)
    WHERE is_default_fallback = TRUE;

-- 3. provider_chains_v2 (scope + content_mode aware)
CREATE TABLE IF NOT EXISTS provider_chains_v2 (
    id                BIGSERIAL    PRIMARY KEY,
    scope             VARCHAR(20)  NOT NULL DEFAULT 'workspace',
    scope_id          VARCHAR(120),                 -- NULL for workspace/system scope
    content_mode      VARCHAR(40),                  -- NULL = applies to all modes
    category          VARCHAR(40)  NOT NULL REFERENCES provider_categories(name),
    position          SMALLINT     NOT NULL,
    credential_id     BIGINT       NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    fallback_strategy VARCHAR(20)  NOT NULL DEFAULT 'on_error',
    created_by        INTEGER,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chains_v2_scope_chk CHECK (scope IN
        ('system','workspace','brand','channel','project')),
    CONSTRAINT chains_v2_strategy_chk CHECK (fallback_strategy IN
        ('on_error','on_rate_limit','on_timeout','always','manual')),
    CONSTRAINT chains_v2_content_mode_fk FOREIGN KEY (content_mode)
        REFERENCES content_modes(name) ON DELETE SET NULL
);

-- One credential cannot appear twice in the same (scope, scope_id, mode, category) chain.
CREATE UNIQUE INDEX IF NOT EXISTS chains_v2_unique_member
    ON provider_chains_v2 (
        scope,
        COALESCE(scope_id, ''),
        COALESCE(content_mode, ''),
        category,
        credential_id
    );

-- And no two credentials share a position within the same chain.
CREATE UNIQUE INDEX IF NOT EXISTS chains_v2_unique_position
    ON provider_chains_v2 (
        scope,
        COALESCE(scope_id, ''),
        COALESCE(content_mode, ''),
        category,
        position
    );

-- Resolution lookup index.
CREATE INDEX IF NOT EXISTS chains_v2_resolve_idx
    ON provider_chains_v2 (scope, scope_id, content_mode, category, position);

-- 4. Promote DB-chain resolution to the default path
-- The legacy resolver falls back to env vars when this flag is off; with the
-- v2 chain populated below, flipping it here makes the new path the primary
-- one across the fleet. Idempotent — safe to re-run.
UPDATE feature_flags
   SET enabled = TRUE,
       description = 'Read provider config from DB (workspace/channel + content-mode aware)'
 WHERE key = 'providers.db_chain.enabled';

-- 5. Backfill from the legacy provider_priority_chains table
-- Treat any existing rows as workspace + mode-agnostic, so the new resolver
-- preserves prior behaviour without manual ops intervention.
INSERT INTO provider_chains_v2
    (scope, scope_id, content_mode, category, position, credential_id, fallback_strategy)
SELECT 'workspace', NULL, NULL, ppc.category, ppc.position, ppc.credential_id, ppc.fallback_strategy
  FROM provider_priority_chains ppc
 WHERE NOT EXISTS (
     SELECT 1 FROM provider_chains_v2 c
      WHERE c.scope = 'workspace' AND c.scope_id IS NULL
        AND c.content_mode IS NULL AND c.category = ppc.category
        AND c.credential_id = ppc.credential_id
   );

-- ===== 202605140002_providers_switches.sql =====
-- 202605140002_providers_switches.sql
-- Add per-chain-entry enable/disable switch and supporting indexes.
-- The credential-level `enabled` column already exists on provider_credentials.

ALTER TABLE provider_chains_v2
    ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS provider_chains_v2_enabled_idx
    ON provider_chains_v2(scope, scope_id, content_mode, category, is_enabled);

CREATE INDEX IF NOT EXISTS provider_credentials_enabled_idx
    ON provider_credentials(category, enabled);

-- ===== 202605140003_provider_secrets.sql =====
-- 202605140003_provider_secrets.sql
-- Encrypted-at-rest secret store for the `db` backend in
-- src.providers.secrets.DBBackend. Each row holds a Fernet-encrypted
-- value identified by (path, key). The encryption key is held only in
-- the SECRETS_ENCRYPTION_KEY env var — never in the DB.

CREATE TABLE IF NOT EXISTS provider_secrets (
    id           BIGSERIAL    PRIMARY KEY,
    path         TEXT         NOT NULL,
    key          TEXT         NOT NULL,
    ciphertext   TEXT         NOT NULL,   -- Fernet token (base64)
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (path, key)
);

CREATE INDEX IF NOT EXISTS provider_secrets_path_idx
    ON provider_secrets(path);

-- ===== 202605150001_channel_environment.sql =====
-- Migration 202605150001 — Channel environment isolation
--
-- Adds an `environment` column to the channels table so that
-- test-mode channels and production channels are completely
-- isolated within the same database.
--
-- Test-mode  (green pill in header) → environment = 'test'
-- Prod mode  (red pill in header)   → environment = 'production'

-- Add column (idempotent via IF NOT EXISTS)
ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS environment VARCHAR(10) NOT NULL DEFAULT 'test';

-- Partial index — fast lookups by env (excludes archived clutter)
CREATE INDEX IF NOT EXISTS idx_channels_environment
    ON channels (environment)
    WHERE status != 'archived';

-- Tag any existing channels as 'test' (they were all seed / test data)
UPDATE channels
   SET environment = 'test'
 WHERE environment IS NULL OR environment = '';

-- ===== 202605160001_multitenant_activate.sql =====
-- 202605160001_multitenant_activate.sql
-- Activate multi-tenancy: workspace pointer per user + invite management columns.

-- Workspace context pointer on users
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS active_workspace_id BIGINT
        REFERENCES workspaces(id) ON DELETE SET NULL;

-- Backfill: assign each user to the earliest workspace they're a member of
UPDATE users u
SET active_workspace_id = (
    SELECT wm.workspace_id
    FROM workspace_members wm
    WHERE wm.user_id = u.id
    ORDER BY wm.joined_at ASC
    LIMIT 1
)
WHERE u.active_workspace_id IS NULL;

-- Final fallback: anyone still unset goes to workspace 1
UPDATE users
SET active_workspace_id = 1
WHERE active_workspace_id IS NULL;

CREATE INDEX IF NOT EXISTS users_active_workspace_idx
    ON users(active_workspace_id);

-- Add resent_at tracking to invitations (for rate-limit UX)
ALTER TABLE workspace_invitations
    ADD COLUMN IF NOT EXISTS resent_at TIMESTAMPTZ;

-- Feature flag for multi-tenant enforcement
INSERT INTO feature_flags (key, enabled, description) VALUES
    ('auth.multi_tenant.enabled', TRUE,
     'Workspace isolation via JWT wid claim — registration creates a new workspace')
ON CONFLICT (key) DO NOTHING;
