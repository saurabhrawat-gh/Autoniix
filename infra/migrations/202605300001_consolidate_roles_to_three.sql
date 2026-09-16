-- Migration 202605300001: Consolidate 5 roles to 3 (Owner / Member / Viewer)
-- Story #260 (AE-227). Parent epic #13 (AE-7).
--
-- Locked decisions:
--   - Owner: exactly one per workspace, full permissions, owns billing.
--   - Member: full content/pipeline permissions but no people-management, no billing.
--   - Viewer: read-only.
--   - Existing rows migrated:
--       admin    -> member
--       producer -> member
--       editor   -> member
--       reviewer -> viewer (defensive — 202605190001 already cleared this)
--       analyst  -> viewer (defensive)
--
-- The 32-permission matrix from 202605220001 stays as the internal RBAC
-- engine. This migration only collapses the *visible* role presets.

BEGIN;

-- ── 1. Backfill existing data ──────────────────────────────────────────────
UPDATE users
   SET role = 'member'
 WHERE role IN ('admin', 'producer', 'editor');
UPDATE users
   SET role = 'viewer'
 WHERE role IN ('reviewer', 'analyst');

UPDATE workspace_members
   SET role = 'member'
 WHERE role IN ('admin', 'producer', 'editor');
UPDATE workspace_members
   SET role = 'viewer'
 WHERE role IN ('reviewer', 'analyst');

UPDATE role_bindings
   SET role = 'member'
 WHERE role IN ('admin', 'producer', 'editor');

-- ── 2. Clean up role_permissions for retired roles ────────────────────────
-- These rows would violate the new CHECK constraint below.
DELETE FROM role_permissions
 WHERE role IN ('admin', 'producer', 'editor');

-- ── 3. Replace CHECK constraints ──────────────────────────────────────────
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_chk;
ALTER TABLE users ADD CONSTRAINT users_role_chk
    CHECK (role IN ('owner', 'member', 'viewer'));

ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS wm_role_chk;
ALTER TABLE workspace_members ADD CONSTRAINT wm_role_chk
    CHECK (role IN ('owner', 'member', 'viewer'));

ALTER TABLE role_bindings DROP CONSTRAINT IF EXISTS rb_role_chk;
ALTER TABLE role_bindings ADD CONSTRAINT rb_role_chk
    CHECK (role IN ('owner', 'member', 'viewer', 'external_reviewer'));

ALTER TABLE role_permissions DROP CONSTRAINT IF EXISTS rp_role_chk;
ALTER TABLE role_permissions ADD CONSTRAINT rp_role_chk
    CHECK (role IN ('owner', 'member', 'viewer'));

-- ── 4. Seed permissions for the new 'member' role ─────────────────────────
-- Member = full content/pipeline + read workspace + manage channel creds.
-- Excluded (owner-only): workspace.settings.edit, workspace.billing.*,
--   workspace.members.invite/remove/role.change, workspace.ownership.transfer,
--   workspace.integrations.manage, workspace.audit_log.view.
INSERT INTO role_permissions (role, permission)
VALUES
    ('member', 'workspace.view'),
    ('member', 'workspace.settings.view'),
    ('member', 'workspace.members.view'),
    ('member', 'workspace.integrations.view'),
    ('member', 'channel.view'),
    ('member', 'channel.create'),
    ('member', 'channel.settings.edit'),
    ('member', 'channel.delete'),
    ('member', 'channel.credentials.view.labels'),
    ('member', 'channel.credentials.manage'),
    ('member', 'project.view'),
    ('member', 'project.create'),
    ('member', 'project.edit'),
    ('member', 'project.delete'),
    ('member', 'project.approve'),
    ('member', 'project.publish'),
    ('member', 'job.view'),
    ('member', 'job.trigger'),
    ('member', 'job.cancel'),
    ('member', 'job.retry'),
    ('member', 'analytics.view'),
    ('member', 'analytics.export'),
    ('member', 'credentials.view.labels'),
    ('member', 'credentials.view.manage')
ON CONFLICT DO NOTHING;

COMMIT;
