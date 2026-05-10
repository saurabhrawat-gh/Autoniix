-- Wave 3: DAM — scoped asset store, versions, collections
-- Additive only; does not touch existing asset_library / brand_assets tables.

-- ── dam_assets ────────────────────────────────────────────────────────────────
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

-- ── dam_asset_versions ────────────────────────────────────────────────────────
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

-- ── dam_collections ───────────────────────────────────────────────────────────
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

-- ── dam_brand_kits ────────────────────────────────────────────────────────────
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

-- ── helper trigger: updated_at ─────────────────────────────────────────────
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
