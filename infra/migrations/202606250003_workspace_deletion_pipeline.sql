-- IM-181: Workspace deletion grace-period pipeline
-- Adds schedule + status tracking to workspaces, and a restorable
-- suspension flag to invitations (distinct from hard-cancelled invites).

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS delete_scheduled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS status              VARCHAR(32) NOT NULL DEFAULT 'active';

-- Fast poll for the hard-delete cron job
CREATE INDEX IF NOT EXISTS workspaces_pending_deletion_idx
    ON workspaces (delete_scheduled_at)
    WHERE delete_scheduled_at IS NOT NULL AND deleted_at IS NOT NULL;

-- Separate from cancelled_at (which is a hard user-cancel).
-- suspended_at is set during soft-delete and cleared on cancel-deletion,
-- restoring the invite to its original pending state.
ALTER TABLE workspace_invitations
    ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ;
