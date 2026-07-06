-- 202606080001_provider_workspace_scoping.sql
-- AE-299: Add workspace_id to provider_credentials for per-workspace isolation.
--
-- Without this column all credentials are globally visible across every workspace
-- in the same database. Per the BA decision (one credential set per workspace, with
-- system-level defaults as fallback) each row must be pinned to a specific workspace.
-- NULL = system-level default credential (visible to all workspaces as fallback).
--
-- Additive only — existing rows default to NULL (system scope), preserving
-- current behaviour. Application layer should populate workspace_id on all
-- new credential inserts.

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) ON DELETE CASCADE;

-- Primary lookup: fetch all credentials for a workspace + category.
CREATE INDEX IF NOT EXISTS provider_credentials_workspace_cat_idx
    ON provider_credentials(workspace_id, category, enabled);

-- Used by admin "Wipe workspace credentials" action.
CREATE INDEX IF NOT EXISTS provider_credentials_workspace_idx
    ON provider_credentials(workspace_id);
