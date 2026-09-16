-- 202605180001_provider_credential_scopes.sql
-- Add channel_id and content_mode scope columns to provider_credentials.
-- These enable per-channel and per-content-mode credential overrides without
-- requiring a separate chain entry. NULL = workspace-level (existing behaviour).

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS channel_id  VARCHAR(20) REFERENCES channels(channel_id) ON DELETE SET NULL;

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS content_mode VARCHAR(40);

-- scope_priority: higher number wins in resolve_credential().
-- 0 = workspace-level (default), 10 = channel-scoped, 20 = channel+mode-scoped.
ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS scope_priority SMALLINT NOT NULL DEFAULT 0;

-- Drop the UNIQUE(category, label) constraint — labels must now be unique
-- per (category, channel_id, content_mode) scope. Replace it with a more
-- permissive partial unique index.
ALTER TABLE provider_credentials
    DROP CONSTRAINT IF EXISTS provider_credentials_category_label_key;

CREATE UNIQUE INDEX IF NOT EXISTS provider_credentials_scope_label_uniq
    ON provider_credentials (category, label, COALESCE(channel_id, ''), COALESCE(content_mode, ''));

-- Fast lookup for resolve_credential()
CREATE INDEX IF NOT EXISTS provider_credentials_scope_idx
    ON provider_credentials (category, channel_id, content_mode, enabled, scope_priority DESC);
