-- 202606080002_provider_secret_blob.sql
-- AE-299: Add secret_blob column to provider_credentials for the DB Fernet backend.
--
-- The existing vault_path column stores a reference path pointing to an external
-- Vault/Infisical/env store. The secret_blob column stores the secret itself,
-- Fernet-encrypted with the key at PROVIDERS_FERNET_KEY, directly in PostgreSQL.
--
-- When PROVIDERS_SECRET_BACKEND=db the DBBackend in src/providers/secrets.py
-- reads/writes this column via asyncpg. It is NULL for credentials that use
-- vault_path (env/vault/infisical backends).
--
-- Additive only — NULL = not using db backend. Safe to re-run.

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS secret_blob TEXT;

COMMENT ON COLUMN provider_credentials.secret_blob IS
    'Fernet-encrypted secret for PROVIDERS_SECRET_BACKEND=db. NULL when vault_path backend is active.';
