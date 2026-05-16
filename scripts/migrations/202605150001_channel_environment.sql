-- ════════════════════════════════════════════════════════════
-- Migration 202605150001 — Channel environment isolation
--
-- Adds an `environment` column to the channels table so that
-- test-mode channels and production channels are completely
-- isolated within the same database.
--
-- Test-mode  (green pill in header) → environment = 'test'
-- Prod mode  (red pill in header)   → environment = 'production'
-- ════════════════════════════════════════════════════════════

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
