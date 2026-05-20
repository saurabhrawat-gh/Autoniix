-- Migration 202605200001: Activate v2 auth and ensure users table has required columns
--
-- Context: The init migration seeds auth.v2.enabled = FALSE and auth.legacy.enabled = TRUE.
-- After the v2 auth deployment, this migration:
--   1. Flips auth.v2.enabled = TRUE
--   2. Flips auth.legacy.enabled = FALSE  (legacy shared-password login retired)
--   3. Ensures the users table has all columns required by the v2 auth backend
--   4. Ensures the sessions table has all columns required for cookie-based sessions
--
-- This migration is additive and idempotent (safe to re-run).

-- ── 1. Activate v2 auth ────────────────────────────────────────────────────
UPDATE feature_flags
   SET enabled = TRUE,
       updated_at = NOW()
 WHERE key = 'auth.v2.enabled';

UPDATE feature_flags
   SET enabled = FALSE,
       updated_at = NOW()
 WHERE key = 'auth.legacy.enabled';

-- ── 2. Ensure users table has v2 auth columns ─────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_hash         TEXT,
    ADD COLUMN IF NOT EXISTS mfa_secret            TEXT,
    ADD COLUMN IF NOT EXISTS mfa_enabled           BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS disabled              BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_login_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS email_verify_token    TEXT,
    ADD COLUMN IF NOT EXISTS email_verified        BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS password_reset_token  TEXT,
    ADD COLUMN IF NOT EXISTS password_reset_exp    TIMESTAMPTZ;

-- ── 3. Ensure sessions table exists with v2 columns ───────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id                  BIGSERIAL     PRIMARY KEY,
    user_id             INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  TEXT          NOT NULL UNIQUE,
    ip                  VARCHAR(45),
    user_agent          TEXT,
    expires_at          TIMESTAMPTZ   NOT NULL,
    revoked_at          TIMESTAMPTZ,
    rotated_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_user_idx
    ON sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS sessions_valid_idx
    ON sessions(refresh_token_hash)
    WHERE revoked_at IS NULL AND rotated_at IS NULL;

-- ── 4. Workspaces table (required for register endpoint) ──────────────────
CREATE TABLE IF NOT EXISTS workspaces (
    id              BIGSERIAL     PRIMARY KEY,
    name            VARCHAR(200)  NOT NULL,
    slug            VARCHAR(60)   UNIQUE NOT NULL,
    plan            VARCHAR(40)   NOT NULL DEFAULT 'starter',
    owner_user_id   INTEGER       REFERENCES users(id) ON DELETE SET NULL,
    billing_email   VARCHAR(200),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id              BIGSERIAL     PRIMARY KEY,
    workspace_id    INTEGER       NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(40)   NOT NULL DEFAULT 'viewer',
    joined_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id)
);

-- ── 5. Ensure active_workspace_id column exists on users ──────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS active_workspace_id BIGINT
        REFERENCES workspaces(id) ON DELETE SET NULL;

-- ── NOTE: First-admin bootstrap ────────────────────────────────────────────
-- No seed user is inserted here because the password hash must be generated
-- at runtime (argon2 / pbkdf2). To create the first admin user:
--
--   docker compose exec api python - <<'EOF'
--   import asyncio, os
--   os.environ.setdefault("DATABASE_URL", "postgresql://...")
--   async def main():
--       import httpx
--       r = httpx.post("http://localhost:8000/api/v2/auth/register",
--                      json={"email": "admin@autoniix.com",
--                            "password": "YOUR_STRONG_PASSWORD",
--                            "display_name": "Admin"})
--       print(r.status_code, r.json())
--   asyncio.run(main())
--   EOF
--
-- Or simply visit https://dash.autoniix.com/register in a browser.
-- The first registrant automatically receives role='owner'.
