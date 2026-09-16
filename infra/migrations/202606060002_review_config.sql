-- AE-229 (Review-Infra-1): Per-channel review gate configuration (AE-226 epic).
--
-- Adds `review_config` JSONB to the `channels` table and a lightweight
-- `approval_decisions` audit table for per-artifact approval records.
--
-- Idempotent: safe to run multiple times.

-- ────────────────────────────────────────────────────────────
-- 1. review_config JSONB on channels
-- ────────────────────────────────────────────────────────────
-- Schema:
--   {
--     "profile": "hands_off" | "quick" | "standard" | "full_control" | "custom",
--     "gates": {
--       "research_data":        true/false,
--       "brand_alignment_report": true/false,
--       "topic_title":          true/false,
--       "story_script":         true/false,
--       "script_voice_data":    true/false,
--       "script_assets_data":   true/false,
--       "script_direction_data":true/false,
--       "voice_track":          true/false,
--       "scene_images":         true/false,
--       "remotion_v3_json":     true/false,
--       "metadata":             true/false,
--       "thumbnail":            true/false,
--       "final_video":          true/false
--     }
--   }
-- Preset defaults:
--   hands_off    → all gates false
--   quick        → story_script + final_video
--   standard     → topic_title + story_script + metadata + thumbnail + final_video
--   full_control → all 13 gates true
--   custom       → per-gate toggles stored in `gates`

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS review_config JSONB NOT NULL DEFAULT '{
        "profile": "hands_off",
        "gates": {
            "research_data":         false,
            "brand_alignment_report":false,
            "topic_title":           false,
            "story_script":          false,
            "script_voice_data":     false,
            "script_assets_data":    false,
            "script_direction_data": false,
            "voice_track":           false,
            "scene_images":          false,
            "remotion_v3_json":      false,
            "metadata":              false,
            "thumbnail":             false,
            "final_video":           false
        }
    }'::jsonb;

-- ────────────────────────────────────────────────────────────
-- 2. approval_decisions audit table (AE-231 foundation)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approval_decisions (
    id              BIGSERIAL       PRIMARY KEY,
    video_id        VARCHAR(50)     NOT NULL REFERENCES videos(content_id) ON DELETE CASCADE,
    artifact_key    VARCHAR(60)     NOT NULL,
    decision        VARCHAR(20)     NOT NULL CHECK (decision IN ('approved','rejected','needs_edits')),
    decided_by      VARCHAR(50)     NOT NULL,
    comment         TEXT,
    artifact_blob   JSONB,
    decided_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS approval_decisions_video_idx
    ON approval_decisions(video_id, artifact_key, decided_at DESC);
