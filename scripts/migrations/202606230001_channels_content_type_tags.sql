-- Migration: add content_type_tags to channels table
-- Issue: GH #676 / AE-588
-- content_type_tags were sent by the frontend wizard but silently dropped
-- because neither the Rust struct nor the DB column existed.

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS content_type_tags TEXT[] NOT NULL DEFAULT '{}';
