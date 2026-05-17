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
