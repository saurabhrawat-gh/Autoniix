-- Migration 006: Review Collaboration (additive)
-- Adds frame-accurate comments, annotations, approvals, and the content
-- generation trigger queue. Leaves `review_sessions` and `review_comments`
-- untouched — those are owned by migration 004 and the live BFF
-- (`src/services/dashboard/v2/review.py`) still uses that schema.
--
-- Safe to re-run (CREATE … IF NOT EXISTS + DO blocks).

-- Frame-accurate comments (new — supplements 004's review_comments)
CREATE TABLE IF NOT EXISTS frame_comments (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    author_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    timecode_s    NUMERIC(10,3),          -- seconds from start; NULL = general
    body          TEXT NOT NULL,
    resolved      BOOLEAN NOT NULL DEFAULT FALSE,
    parent_id     BIGINT REFERENCES frame_comments(id) ON DELETE SET NULL, -- threads
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_frame_comments_session  ON frame_comments(session_id);
CREATE INDEX IF NOT EXISTS idx_frame_comments_resolved ON frame_comments(session_id, resolved);

-- Annotations (visual overlays on thumbnail / frame)
CREATE TABLE IF NOT EXISTS review_annotations (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    author_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    timecode_s    NUMERIC(10,3),
    kind          TEXT NOT NULL DEFAULT 'rect'   -- rect | arrow | text | circle
                  CHECK (kind IN ('rect','arrow','text','circle')),
    coords        JSONB NOT NULL,                -- {x, y, w, h} or {x1,y1,x2,y2}
    label         TEXT,
    color         TEXT DEFAULT '#f97316',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_annotations_session ON review_annotations(session_id);

-- Approvals (per-reviewer decision)
CREATE TABLE IF NOT EXISTS review_approvals (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    reviewer_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('approved','rejected','needs_edits')),
    note          TEXT,
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, reviewer_id)
);
CREATE INDEX IF NOT EXISTS idx_approvals_session ON review_approvals(session_id);

-- Content generation queue (trigger tracking)
CREATE TABLE IF NOT EXISTS content_triggers (
    id            BIGSERIAL PRIMARY KEY,
    channel_id    TEXT NOT NULL,
    content_mode  TEXT NOT NULL DEFAULT 'long_form',
    topic_hint    TEXT,
    scheduled_for TIMESTAMPTZ,
    triggered_by  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','done','failed','cancelled')),
    content_id    TEXT,                          -- filled once workflow starts
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_triggers_channel ON content_triggers(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_triggers_status  ON content_triggers(status);

-- updated_at triggers (only for tables that own an updated_at column)
CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_frame_comments_upd') THEN
    CREATE TRIGGER trg_frame_comments_upd
      BEFORE UPDATE ON frame_comments
      FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_content_triggers_upd') THEN
    CREATE TRIGGER trg_content_triggers_upd
      BEFORE UPDATE ON content_triggers
      FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
  END IF;
END $$;
