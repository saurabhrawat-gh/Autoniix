-- Migration 202605190001: Tighten role constraints to the 5-role model
-- Removes 'reviewer' from users table and both workspace tables.
-- Adds 'producer' to users table (was already in workspace_members).
-- Data migration for reviewer/analyst was done in 202605170002.

-- Safety: migrate any remaining reviewer/analyst at the users level
UPDATE users SET role = 'viewer' WHERE role IN ('reviewer', 'analyst');

-- users table: owner | admin | producer | editor | viewer
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_chk;
ALTER TABLE users ADD CONSTRAINT users_role_chk
    CHECK (role IN ('owner', 'admin', 'producer', 'editor', 'viewer'));

-- workspace_members: same 5 roles only
ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS wm_role_chk;
ALTER TABLE workspace_members ADD CONSTRAINT wm_role_chk
    CHECK (role IN ('owner', 'admin', 'producer', 'editor', 'viewer'));

-- role_bindings: 5 roles + external_reviewer (kept for review session use)
ALTER TABLE role_bindings DROP CONSTRAINT IF EXISTS rb_role_chk;
ALTER TABLE role_bindings ADD CONSTRAINT rb_role_chk
    CHECK (role IN ('owner', 'admin', 'producer', 'editor', 'viewer', 'external_reviewer'));
