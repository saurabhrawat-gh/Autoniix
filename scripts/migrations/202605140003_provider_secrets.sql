-- 202605140003_provider_secrets.sql
-- Encrypted-at-rest secret store for the `db` backend in
-- src.providers.secrets.DBBackend. Each row holds a Fernet-encrypted
-- value identified by (path, key). The encryption key is held only in
-- the SECRETS_ENCRYPTION_KEY env var — never in the DB.

CREATE TABLE IF NOT EXISTS provider_secrets (
    id           BIGSERIAL    PRIMARY KEY,
    path         TEXT         NOT NULL,
    key          TEXT         NOT NULL,
    ciphertext   TEXT         NOT NULL,   -- Fernet token (base64)
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (path, key)
);

CREATE INDEX IF NOT EXISTS provider_secrets_path_idx
    ON provider_secrets(path);
