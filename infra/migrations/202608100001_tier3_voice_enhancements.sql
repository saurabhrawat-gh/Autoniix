-- Migration: Tier 3 Voice Service - Word Alignment & Hero Cache
-- Date: 2026-08-10
-- Purpose: Add hero take caching and word alignment storage

-- Hero take cache for reusing high-quality takes
CREATE TABLE IF NOT EXISTS voice_hero_cache (
    id SERIAL PRIMARY KEY,
    channel_id TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    audio_url TEXT NOT NULL,
    quality_score FLOAT NOT NULL,
    tts_params JSONB,
    word_alignment JSONB,
    duration_ms INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE (channel_id, text_hash)
);

CREATE INDEX idx_voice_hero_cache_channel ON voice_hero_cache (channel_id);
CREATE INDEX idx_voice_hero_cache_expires ON voice_hero_cache (expires_at);
CREATE INDEX idx_voice_hero_cache_quality ON voice_hero_cache (quality_score DESC);

COMMENT ON TABLE voice_hero_cache IS 'Tier 3: Cache hero moment takes for reuse across videos';
COMMENT ON COLUMN voice_hero_cache.text_hash IS 'SHA-256 hash of narration text for deduplication';
COMMENT ON COLUMN voice_hero_cache.word_alignment IS 'Normalized word-level timestamps from Inworld/WhisperX';
COMMENT ON COLUMN voice_hero_cache.duration_ms IS 'Measured duration via ffprobe (not estimated)';

-- Voice generation history for analytics
CREATE TABLE IF NOT EXISTS voice_generation_log (
    id SERIAL PRIMARY KEY,
    content_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    voice_id TEXT,
    total_duration_ms INT NOT NULL,
    word_count INT NOT NULL,
    sentence_count INT NOT NULL,
    quality_score FLOAT NOT NULL,
    cost_usd FLOAT NOT NULL,
    has_word_alignment BOOLEAN DEFAULT FALSE,
    duration_measured BOOLEAN DEFAULT FALSE,
    multi_take_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_log_content ON voice_generation_log (content_id);
CREATE INDEX idx_voice_log_channel ON voice_generation_log (channel_id);
CREATE INDEX idx_voice_log_created ON voice_generation_log (created_at DESC);

COMMENT ON TABLE voice_generation_log IS 'Tier 3: Track voice generation metrics for quality analysis';
COMMENT ON COLUMN voice_generation_log.has_word_alignment IS 'Whether word-level timestamps were extracted';
COMMENT ON COLUMN voice_generation_log.duration_measured IS 'Whether duration was measured via ffprobe vs estimated';
