-- 202605290001_default_workspace_remediation.sql
-- AE-222: Remediate the synthetic "Default Workspace" trap left by the
-- 202605160050_init.sql backfill.
--
-- Background:
--   The init migration inserts a workspace row (id=1, name='Default Workspace',
--   slug='default') and backfills every then-existing user into it via
--   workspace_members. Post-AE-217, this means legacy seed accounts log in,
--   land on a workspace they never named, and never see the onboarding wizard
--   because the WorkspaceGuard only redirected when the workspace list was
--   empty.
--
-- The accompanying code change extends GET /auth/workspaces to return an
-- `onboarding_completed` boolean per workspace, and the frontend guard now
-- redirects users whose active workspace has not been onboarded.
--
-- This migration is the data-layer counterpart: ensure no stale
-- `onboarding.completed = true` row exists in entity_settings for the
-- synthetic Default Workspace, so legacy users definitely flow through the
-- onboarding wizard on their next login.
--
-- Idempotent and safe to re-run.

DO $$
DECLARE
    synthetic_id BIGINT;
BEGIN
    -- Identify the synthetic workspace ONLY if it is still untouched
    -- (name unchanged AND slug unchanged). If the owner already renamed it,
    -- this migration is a no-op for that workspace.
    SELECT id INTO synthetic_id
      FROM workspaces
     WHERE id = 1
       AND name = 'Default Workspace'
       AND slug = 'default';

    IF synthetic_id IS NULL THEN
        RAISE NOTICE 'AE-222: No untouched synthetic Default Workspace found. Skipping.';
        RETURN;
    END IF;

    -- Remove any stale onboarding completion flag so the wizard fires.
    DELETE FROM entity_settings
     WHERE scope = 'workspace'
       AND scope_id = synthetic_id::TEXT
       AND key = 'onboarding';

    RAISE NOTICE 'AE-222: Cleared onboarding settings for synthetic workspace id=%.', synthetic_id;
END $$;
