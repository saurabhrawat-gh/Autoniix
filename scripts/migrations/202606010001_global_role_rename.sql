-- Migration 202606010001: Rename global (platform-level) roles on users table
--
-- Separates the platform role namespace from the workspace role namespace.
-- Before: users.role IN ('owner', 'member', 'viewer')  ← identical to workspace_members.role (confusing)
-- After:  users.role IN ('superadmin', 'user')
--         workspace_members.role stays AS ('owner', 'member', 'viewer') — unchanged
--
-- Mapping:
--   users.role='owner'            → 'superadmin'  (platform admin — can manage all users)
--   users.role='member'|'viewer'  → 'user'         (regular registrant — workspace roles govern access)
--
-- Related: AE-279 (JWT encodes workspace role not global role)

-- ── 1. Backfill existing data ─────────────────────────────────────────────────
UPDATE users SET role = 'superadmin' WHERE role = 'owner';
UPDATE users SET role = 'user' WHERE role IN ('member', 'viewer');

-- ── 2. Replace CHECK constraint on users table ────────────────────────────────
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_chk;
ALTER TABLE users ADD CONSTRAINT users_role_chk
    CHECK (role IN ('superadmin', 'user'));

-- workspace_members.role, role_permissions.role, role_bindings.role are all
-- WORKSPACE-SCOPED and intentionally use 'owner'|'member'|'viewer'. No change.
