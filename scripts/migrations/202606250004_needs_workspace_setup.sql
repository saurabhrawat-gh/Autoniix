-- IM-183: Orphaned user protection
-- Adds `needs_workspace_setup` flag to users so the system can redirect
-- owners who were force-deleted (superadmin) to the onboarding wizard on
-- next login instead of leaving them in a broken workspace-less state.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS needs_workspace_setup BOOLEAN NOT NULL DEFAULT FALSE;
