-- 202605140002_providers_switches.sql
-- Add per-chain-entry enable/disable switch and supporting indexes.
-- The credential-level `enabled` column already exists on provider_credentials.

ALTER TABLE provider_chains_v2
    ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS provider_chains_v2_enabled_idx
    ON provider_chains_v2(scope, scope_id, content_mode, category, is_enabled);

CREATE INDEX IF NOT EXISTS provider_credentials_enabled_idx
    ON provider_credentials(category, enabled);
