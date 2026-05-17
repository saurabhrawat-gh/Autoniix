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
