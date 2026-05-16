-- 202605160001_multitenant_activate.sql
-- Activate multi-tenancy: workspace pointer per user + invite management columns.

-- Workspace context pointer on users
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS active_workspace_id BIGINT
        REFERENCES workspaces(id) ON DELETE SET NULL;

-- Backfill: assign each user to the earliest workspace they're a member of
UPDATE users u
SET active_workspace_id = (
    SELECT wm.workspace_id
    FROM workspace_members wm
    WHERE wm.user_id = u.id
    ORDER BY wm.joined_at ASC
    LIMIT 1
)
WHERE u.active_workspace_id IS NULL;

-- Final fallback: anyone still unset goes to workspace 1
UPDATE users
SET active_workspace_id = 1
WHERE active_workspace_id IS NULL;

CREATE INDEX IF NOT EXISTS users_active_workspace_idx
    ON users(active_workspace_id);

-- Add resent_at tracking to invitations (for rate-limit UX)
ALTER TABLE workspace_invitations
    ADD COLUMN IF NOT EXISTS resent_at TIMESTAMPTZ;

-- Feature flag for multi-tenant enforcement
INSERT INTO feature_flags (key, enabled, description) VALUES
    ('auth.multi_tenant.enabled', TRUE,
     'Workspace isolation via JWT wid claim — registration creates a new workspace')
ON CONFLICT (key) DO NOTHING;
