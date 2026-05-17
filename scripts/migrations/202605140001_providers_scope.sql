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
