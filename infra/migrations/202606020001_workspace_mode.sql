-- Migration 202606020001: Add collaboration mode to workspaces
--
-- Introduces a `mode` column on workspaces:
--   solo  — single user; invite functionality is disabled (default for NEW workspaces created after this migration)
--   teams — multi-user; invite functionality is enabled
--
-- Existing workspaces default to 'teams' so that current invite workflows
-- continue to function without any manual action from workspace owners.
-- New workspaces are inserted with mode='solo' via auth.py registration.
--
-- Related: AE-284

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS mode VARCHAR(10) NOT NULL DEFAULT 'teams'
        CONSTRAINT workspaces_mode_chk CHECK (mode IN ('solo', 'teams'));
