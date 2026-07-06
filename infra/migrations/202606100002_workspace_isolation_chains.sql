-- 202606100002_workspace_isolation_chains.sql
-- AE-324: Full workspace isolation for provider chains and credentials.
--
-- Root cause: provider_chains_v2 had no workspace_id column, so every workspace
-- shared the same chain rows. provider_credentials allowed workspace_id IS NULL
-- rows to bleed into every new workspace as "system defaults".
--
-- Fix:
--   1. Backfill workspace_id = 1 on all credentials where it is NULL (they were
--      created before multi-workspace existed and belong to the original workspace).
--   2. Add workspace_id to provider_chains_v2 and backfill from the credential.
--   3. Drop the NULL-as-fallback semantic — every row now has an explicit owner.

-- Step 1: backfill credentials
UPDATE provider_credentials
   SET workspace_id = 1
 WHERE workspace_id IS NULL;

-- Step 2: add workspace_id to provider_chains_v2
ALTER TABLE provider_chains_v2
    ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) ON DELETE CASCADE;

-- Step 3: backfill chains from their attached credential's workspace
UPDATE provider_chains_v2 c
   SET workspace_id = pc.workspace_id
  FROM provider_credentials pc
 WHERE c.credential_id = pc.id
   AND c.workspace_id IS NULL;

-- Step 4: any orphaned chain rows (no credential) default to workspace 1
UPDATE provider_chains_v2
   SET workspace_id = 1
 WHERE workspace_id IS NULL;

-- Step 5: index for workspace-scoped chain lookups
CREATE INDEX IF NOT EXISTS provider_chains_v2_workspace_cat_idx
    ON provider_chains_v2(workspace_id, category, scope);
