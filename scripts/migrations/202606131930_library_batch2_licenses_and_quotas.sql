-- 202606131930_library_batch2_licenses_and_quotas.sql
-- Library Sprint batch 2: AE-363 (license catalogue) + AE-364 (storage quotas).
--
-- AE-363:
--   No new table — leverages existing dam_assets.license / license_url /
--   expires_at columns. This migration only seeds the controlled
--   vocabulary into system_config so the upload form can read it.
--
-- AE-364:
--   storage_quotas — per-scope quota / used / calculated_at row, refreshed
--   by an aggregator the dashboard can trigger on demand (a scheduled job
--   is a follow-up). Seeded with sensible defaults (per the ticket spec).
--
-- All statements idempotent.


-- ─────────────────────────────────────────────────────────────────────────────
-- AE-363: license catalogue
-- ─────────────────────────────────────────────────────────────────────────────
-- We store the catalogue as a single system_config row so the dashboard
-- can edit it without a deploy. The default value mirrors the ticket spec.
-- The catalogue is intentionally NOT a hard CHECK constraint on
-- dam_assets.license — existing rows would otherwise need a back-fill,
-- and operators sometimes need to use a custom license string per asset.

-- The existing system_config uses (config_key, config_value TEXT) — JSON is
-- stored as a serialised string and parsed client-side. We follow the same
-- convention here.

INSERT INTO system_config (config_key, config_value, description) VALUES (
    'library.license_catalogue',
    '[
        {"id": "creative-commons-0",      "label": "CC0 (Public Domain)",            "commercial": true,  "attribution": false},
        {"id": "creative-commons-by",     "label": "CC BY (Attribution Required)",   "commercial": true,  "attribution": true},
        {"id": "creative-commons-by-sa",  "label": "CC BY-SA (Share-Alike)",         "commercial": true,  "attribution": true},
        {"id": "royalty-free",            "label": "Royalty-Free",                   "commercial": true,  "attribution": false},
        {"id": "royalty-free-limited",    "label": "Royalty-Free (Limited)",         "commercial": true,  "attribution": false},
        {"id": "editorial-only",          "label": "Editorial Only (No Commercial)", "commercial": false, "attribution": true},
        {"id": "proprietary-internal",    "label": "Proprietary / Internal",         "commercial": true,  "attribution": false},
        {"id": "licensed-envato",         "label": "Licensed via Envato",            "commercial": true,  "attribution": false},
        {"id": "licensed-pixabay",        "label": "Licensed via Pixabay",           "commercial": true,  "attribution": false},
        {"id": "licensed-shutterstock",   "label": "Licensed via Shutterstock",      "commercial": true,  "attribution": false},
        {"id": "unknown",                 "label": "Unknown (Flagged)",              "commercial": false, "attribution": true}
    ]',
    'AE-363: controlled vocabulary for dam_assets.license. Dashboard upload form reads this; row is editable so new license types can be added without a deploy.'
) ON CONFLICT (config_key) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- AE-364: storage_quotas
-- ─────────────────────────────────────────────────────────────────────────────

-- scope_id is NOT NULL with a sentinel '' for the system scope. PostgreSQL
-- treats NULLs as distinct under unique constraints, which would silently
-- defeat ON CONFLICT here.
CREATE TABLE IF NOT EXISTS storage_quotas (
    scope          VARCHAR(20)   NOT NULL
                   CHECK (scope IN ('system','workspace','brand','channel','project')),
    scope_id       VARCHAR(100)  NOT NULL DEFAULT '',  -- '' for scope='system' (single bucket)
    quota_bytes    BIGINT        NOT NULL,             -- 0 = no quota / unlimited
    used_bytes     BIGINT        NOT NULL DEFAULT 0,
    calculated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, scope_id)
);

-- Defaults — operators override per-scope via PUT /library/dam/quotas later.
-- Values from the AE-364 ticket spec.
INSERT INTO storage_quotas (scope, scope_id, quota_bytes) VALUES
    ('system', '', 0)                                  -- unlimited
ON CONFLICT (scope, scope_id) DO NOTHING;

-- Default quota knobs that the aggregator falls back to when a row is
-- missing for a scope it just discovered. JSON in system_config so an
-- operator can change them without a migration.
INSERT INTO system_config (config_key, config_value, description) VALUES (
    'library.default_quotas',
    '{
        "workspace_bytes":  107374182400,
        "brand_bytes":       26843545600,
        "channel_bytes":     10737418240,
        "project_bytes":      5368709120
    }',
    'AE-364: default quota_bytes used by the storage-quota aggregator when a (scope, scope_id) row does not yet exist. 100 GB / 25 GB / 10 GB / 5 GB.'
) ON CONFLICT (config_key) DO NOTHING;
