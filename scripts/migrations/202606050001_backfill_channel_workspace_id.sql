-- Migration: 202606050001_backfill_channel_workspace_id
--
-- Root cause: create_channel INSERT never included workspace_id, so all
-- channels created after the init migration have workspace_id = NULL.
-- The DELETE endpoint checks channel.workspace_id = actor.workspace_id,
-- so NULL channels could never be deleted — they appeared as "not found".
--
-- Fix (code): channels.py create_channel now writes actor.workspace_id ($44).
-- Fix (data):
--   Step 1 — Backfill truly orphaned channels (no workspace link at all)
--             to the legacy default workspace (id=1), consistent with the
--             original 202605160050_init.sql backfill.
--   Step 2 — Reassign specific channels to their correct workspace.
--             Edit the WHERE clause below for each channel you want to move.

-- Step 1: backfill channels with no workspace association
UPDATE channels
SET workspace_id = 1
WHERE workspace_id IS NULL;

-- Step 2: reassign channels to their actual workspace.
--
-- Usage: replace 'YOUR_CHANNEL_ID' with the channel_id (e.g. 'test_97db')
--        and 'Your Workspace Name' with the workspace name (e.g. 'Roar Studios').
--
-- This is intentionally left as a template — run it manually or via psql
-- after confirming the workspace name.
--
-- UPDATE channels
-- SET workspace_id = (
--     SELECT id FROM workspaces WHERE name = 'Roar Studios' LIMIT 1
-- )
-- WHERE channel_id = 'test_97db';
