-- IM-180: Workspace soft-delete support
-- Adds deleted_at to workspaces for grace-period deletion,
-- and cancelled_at to workspace_invitations so pending invites
-- are atomically invalidated when a workspace is soft-deleted.

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Partial index so all active-workspace queries stay fast
CREATE INDEX IF NOT EXISTS workspaces_active_idx
    ON workspaces (id) WHERE deleted_at IS NULL;

ALTER TABLE workspace_invitations
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
