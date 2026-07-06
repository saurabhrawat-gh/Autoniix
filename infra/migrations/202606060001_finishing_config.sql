-- AE-296 / AE-294: Professional Finishing Pipeline (Phase 1A) data foundation.
--
-- Adds the per-channel finishing configuration table and the three finishing
-- bookkeeping columns on the rendered-video table.
--
-- NOTE on schema mapping: the BA-locked spec (AE-293) referenced a `content`
-- table and a UUID `channels(id)` PK. The live schema uses the `videos` table
-- (content_id VARCHAR(50)) and `channels(channel_id VARCHAR(20))`, so the FK and
-- the new columns are mapped onto the real tables here.
--
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS channel_finishing_config (
    channel_id              VARCHAR(20)  PRIMARY KEY
                                REFERENCES channels(channel_id) ON DELETE CASCADE,
    require_resolve_finish  BOOLEAN      NOT NULL DEFAULT FALSE,
    color_grade_preset      VARCHAR(50)  NOT NULL DEFAULT 'cinematic',
    audio_denoise           BOOLEAN      NOT NULL DEFAULT TRUE,
    audio_eq                BOOLEAN      NOT NULL DEFAULT TRUE,
    audio_compress          BOOLEAN      NOT NULL DEFAULT TRUE,
    audio_music_duck        BOOLEAN      NOT NULL DEFAULT TRUE,
    audio_loudness_lufs     DECIMAL(4,1) NOT NULL DEFAULT -14.0,
    audio_true_peak_dbtps   DECIMAL(4,1) NOT NULL DEFAULT -1.5,
    output_prores_archive   BOOLEAN      NOT NULL DEFAULT FALSE,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT channel_finishing_preset_valid CHECK (
        color_grade_preset IN (
            'cinematic', 'clean_bright', 'warm_gold', 'cool_blue',
            'vintage', 'documentary', 'neon_dark'
        )
    ),
    CONSTRAINT channel_finishing_loudness_range CHECK (
        audio_loudness_lufs BETWEEN -24.0 AND -9.0
    ),
    CONSTRAINT channel_finishing_true_peak_range CHECK (
        audio_true_peak_dbtps BETWEEN -6.0 AND -0.1
    )
);

-- Finishing bookkeeping on the rendered-video table.
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS finishing_skipped     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS finishing_preset_used VARCHAR(50),
    ADD COLUMN IF NOT EXISTS prores_path           TEXT;

-- Seed a default finishing config row for every existing channel.
INSERT INTO channel_finishing_config (channel_id)
    SELECT channel_id FROM channels
    ON CONFLICT (channel_id) DO NOTHING;
