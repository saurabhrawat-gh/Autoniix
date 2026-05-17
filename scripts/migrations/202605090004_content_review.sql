-- 202605090004_content_review.sql
-- Phase 3 (S2 + S5): Generated Content browse + Manual Review.

-- Additive columns on videos
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS review_state         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS review_assigned_to   INTEGER,
    ADD COLUMN IF NOT EXISTS review_notes_count   INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS authenticity_score   DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS uniqueness_score     DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS title_embedding      vector(384),
    ADD COLUMN IF NOT EXISTS published_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS scheduled_at         TIMESTAMPTZ;

-- Generated week bucket. Postgres GENERATED stored cols can't reference
-- mutable funcs; date_trunc with constant timezone is immutable in pg15+.
-- Use a regular column + trigger for portability.
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS week_bucket DATE;

CREATE OR REPLACE FUNCTION videos_set_week_bucket() RETURNS TRIGGER AS $$
BEGIN
    NEW.week_bucket := date_trunc('week', COALESCE(NEW.created_at, NOW()))::date;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS videos_week_bucket_trg ON videos;
CREATE TRIGGER videos_week_bucket_trg
    BEFORE INSERT OR UPDATE OF created_at ON videos
    FOR EACH ROW EXECUTE FUNCTION videos_set_week_bucket();

-- Backfill existing rows
UPDATE videos
   SET week_bucket = date_trunc('week', created_at)::date
 WHERE week_bucket IS NULL;

CREATE INDEX IF NOT EXISTS videos_channel_week_idx
    ON videos(channel_id, week_bucket DESC);
CREATE INDEX IF NOT EXISTS videos_channel_created_idx
    ON videos(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS videos_review_state_idx
    ON videos(review_state) WHERE review_state IS NOT NULL;

-- Review sessions
CREATE TABLE IF NOT EXISTS review_sessions (
    id            BIGSERIAL     PRIMARY KEY,
    video_id      VARCHAR(50)   NOT NULL,  -- videos.content_id
    channel_id    VARCHAR(20)   NOT NULL,
    state         VARCHAR(20)   NOT NULL DEFAULT 'pending',
    opened_by     INTEGER,
    opened_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    decided_by    INTEGER,
    decided_at    TIMESTAMPTZ,
    summary       TEXT,
    expires_at    TIMESTAMPTZ,
    CONSTRAINT review_sessions_state_chk CHECK (state IN
        ('pending','approved','needs_edits','rejected','regenerating','timed_out'))
);
CREATE INDEX IF NOT EXISTS review_sessions_video_idx
    ON review_sessions(video_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS review_sessions_state_idx
    ON review_sessions(state, opened_at DESC) WHERE state = 'pending';

CREATE TABLE IF NOT EXISTS review_comments (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  BIGINT       NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    artifact    VARCHAR(20)  NOT NULL,
    anchor      JSONB,
    author_id   INTEGER,
    body        TEXT         NOT NULL,
    parent_id   BIGINT       REFERENCES review_comments(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT review_comments_artifact_chk CHECK (artifact IN
        ('script','thumbnail','title','description','tags','voice','timeline','seo','general'))
);
CREATE INDEX IF NOT EXISTS review_comments_session_idx
    ON review_comments(session_id, created_at);

-- Script & thumbnail versioning
CREATE TABLE IF NOT EXISTS script_versions (
    id              BIGSERIAL    PRIMARY KEY,
    video_id        VARCHAR(50)  NOT NULL,
    version         SMALLINT     NOT NULL,
    source          VARCHAR(20)  NOT NULL,
    content         JSONB        NOT NULL,
    diff_summary    TEXT,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, version),
    CONSTRAINT script_versions_source_chk CHECK (source IN
        ('ai_initial','ai_section','ai_full','human','tone_change','shorten','expand','restore'))
);
CREATE INDEX IF NOT EXISTS script_versions_video_idx
    ON script_versions(video_id, version DESC);

CREATE TABLE IF NOT EXISTS thumbnail_versions (
    id            BIGSERIAL    PRIMARY KEY,
    video_id      VARCHAR(50)  NOT NULL,
    version       SMALLINT     NOT NULL,
    source        VARCHAR(20)  NOT NULL,    -- ai|human
    minio_key     TEXT         NOT NULL,
    prompt        TEXT,
    ctr_pred      DECIMAL(5,4),
    composition   JSONB,
    created_by    INTEGER,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (video_id, version)
);
CREATE INDEX IF NOT EXISTS thumbnail_versions_video_idx
    ON thumbnail_versions(video_id, version DESC);

-- Postgres FTS for content search
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS title_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title,'') || ' ' || coalesce(topic,'') || ' ' || coalesce(selected_hook,'')
        )
    ) STORED;
CREATE INDEX IF NOT EXISTS videos_title_tsv_idx ON videos USING gin(title_tsv);
