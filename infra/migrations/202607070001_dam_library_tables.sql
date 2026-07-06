-- Migration: B3 Library cluster — DAM tables
-- Creates: dam_assets, dam_asset_versions, dam_collections, dam_brand_kits,
--          media_jobs, media_renditions, storage_quotas

-- ── dam_assets ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dam_assets (
    id            BIGSERIAL    PRIMARY KEY,
    scope         VARCHAR(50)  NOT NULL DEFAULT 'workspace',
    scope_id      TEXT,
    kind          VARCHAR(50)  NOT NULL,
    display_name  TEXT         NOT NULL,
    mime_type     TEXT,
    bytes         BIGINT,
    content_hash  VARCHAR(64),
    storage_key   TEXT,
    thumbnail_key TEXT,
    origin        VARCHAR(50)  NOT NULL DEFAULT 'upload',
    license       TEXT,
    license_url   TEXT,
    expires_at    TIMESTAMPTZ,
    tags          TEXT[]       NOT NULL DEFAULT '{}',
    ai_tags       JSONB        NOT NULL DEFAULT '{}',
    metadata      JSONB        NOT NULL DEFAULT '{}',
    created_by    TEXT,
    deleted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dam_assets_scope    ON dam_assets (scope, scope_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_kind     ON dam_assets (kind)            WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_hash     ON dam_assets (content_hash)    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_dam_assets_tags     ON dam_assets USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_dam_assets_ai_tags  ON dam_assets USING GIN (ai_tags);
CREATE INDEX IF NOT EXISTS idx_dam_assets_fts      ON dam_assets USING GIN (to_tsvector('english', display_name));

-- ── dam_asset_versions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dam_asset_versions (
    id           BIGSERIAL   PRIMARY KEY,
    asset_id     BIGINT      NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    version_no   INT         NOT NULL,
    bytes        BIGINT,
    content_hash VARCHAR(64),
    storage_key  TEXT,
    note         TEXT,
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_id, version_no)
);

-- ── dam_collections ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dam_collections (
    id             BIGSERIAL   PRIMARY KEY,
    scope          VARCHAR(50) NOT NULL DEFAULT 'workspace',
    scope_id       TEXT,
    name           TEXT        NOT NULL,
    description    TEXT,
    kind           VARCHAR(20) NOT NULL DEFAULT 'manual',
    query          JSONB       NOT NULL DEFAULT '{}',
    asset_ids      BIGINT[]    NOT NULL DEFAULT '{}',
    cover_asset_id BIGINT,
    owner_id       TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dam_collections_scope ON dam_collections (scope, scope_id);

-- ── dam_brand_kits ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dam_brand_kits (
    id              BIGSERIAL   PRIMARY KEY,
    scope           VARCHAR(50) NOT NULL DEFAULT 'brand',
    scope_id        TEXT,
    name            TEXT        NOT NULL,
    version_no      INT         NOT NULL DEFAULT 1,
    logo_asset_ids  BIGINT[]    NOT NULL DEFAULT '{}',
    palette         JSONB       NOT NULL DEFAULT '{}',
    font_asset_ids  BIGINT[]    NOT NULL DEFAULT '{}',
    lut_asset_id    BIGINT,
    intro_asset_id  BIGINT,
    outro_asset_id  BIGINT,
    voice_sample_id BIGINT,
    motion_presets  JSONB       NOT NULL DEFAULT '{}',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dam_brand_kits_scope ON dam_brand_kits (scope, scope_id);

-- ── media_jobs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media_jobs (
    id           BIGSERIAL   PRIMARY KEY,
    asset_id     BIGINT      NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    kind         VARCHAR(50) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority     INT         NOT NULL DEFAULT 5,
    max_attempts INT         NOT NULL DEFAULT 3,
    attempts     INT         NOT NULL DEFAULT 0,
    worker_id    TEXT,
    result       JSONB       NOT NULL DEFAULT 'null',
    error        TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_jobs_asset  ON media_jobs (asset_id);
CREATE INDEX IF NOT EXISTS idx_media_jobs_status ON media_jobs (status) WHERE status IN ('pending','running');

-- ── media_renditions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media_renditions (
    id             BIGSERIAL   PRIMARY KEY,
    asset_id       BIGINT      NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    rendition_kind VARCHAR(50) NOT NULL,
    storage_key    TEXT,
    codec          TEXT,
    width          INT,
    height         INT,
    bitrate_kbps   INT,
    duration_ms    INT,
    bytes          BIGINT,
    metadata       JSONB       NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_id, rendition_kind)
);

-- ── storage_quotas ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS storage_quotas (
    scope         VARCHAR(50) NOT NULL,
    scope_id      TEXT        NOT NULL DEFAULT '',
    quota_bytes   BIGINT      NOT NULL DEFAULT 0,
    used_bytes    BIGINT      NOT NULL DEFAULT 0,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, scope_id)
);
