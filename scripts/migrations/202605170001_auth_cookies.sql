-- Migration 202605170001: Auth cookie support + refresh token rotation
-- Adds rotated_at to sessions for single-use refresh token enforcement.
-- Adds password_reset_token columns to users for direct reset flow support.

-- Refresh token rotation: mark a session as rotated (consumed) when a new one is issued
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS rotated_at TIMESTAMPTZ;

-- Index to quickly find sessions that are still valid (not revoked or rotated)
CREATE INDEX IF NOT EXISTS sessions_valid_idx
    ON sessions(refresh_token_hash)
    WHERE revoked_at IS NULL AND rotated_at IS NULL;
