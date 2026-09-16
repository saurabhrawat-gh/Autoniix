-- Migration 202605170002: Workspace integrations + 5-role cleanup
-- Creates workspace_integrations table for per-workspace Slack webhook storage.
-- Migrates legacy reviewer + analyst roles to viewer.

-- Per-workspace integration config (Slack webhook, future: webhooks, etc.)
CREATE TABLE IF NOT EXISTS workspace_integrations (
    id                  BIGSERIAL   PRIMARY KEY,
    workspace_id        BIGINT      NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    slack_webhook_url   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id)
);

-- Migrate legacy roles: reviewer + analyst → viewer (5-role model)
UPDATE workspace_members
   SET role = 'viewer'
 WHERE role IN ('reviewer', 'analyst');

-- Migrate pending invitations that were issued with legacy roles
UPDATE workspace_invitations
   SET role = 'viewer'
 WHERE role IN ('reviewer', 'analyst')
   AND accepted_at IS NULL;
