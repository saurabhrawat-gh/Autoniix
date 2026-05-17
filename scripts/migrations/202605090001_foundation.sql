-- 202605090001_foundation.sql
-- Phase 0: Foundations
-- Adds: schema_migrations tracker, feature_flags, audit_log_v2.
-- All additive. Safe to re-run.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version       VARCHAR(40)   PRIMARY KEY,
    applied_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    checksum      VARCHAR(64)   NOT NULL,
    description   TEXT
);

-- Feature flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id            BIGSERIAL     PRIMARY KEY,
    key           VARCHAR(100)  UNIQUE NOT NULL,
    enabled       BOOLEAN       NOT NULL DEFAULT FALSE,
    description   TEXT,
    payload       JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO feature_flags (key, enabled, description) VALUES
    ('ui.v2.enabled',           FALSE, 'Show /dashboard/v2 routes and v2 components'),
    ('auth.legacy.enabled',     TRUE,  'Allow shared-password login (deprecated)'),
    ('auth.v2.enabled',         FALSE, 'Enable real users / sessions / MFA'),
    ('providers.db_chain.enabled', FALSE, 'Read provider config from DB instead of env'),
    ('review.gate.enabled',     FALSE, 'Pause workflows for human review when channel.human_review_required != never'),
    ('notifications.slack.enabled', FALSE, 'Route notifications to Slack'),
    ('safety.uniqueness_guard.enabled', FALSE, 'Reject videos > 0.92 cosine to last 30 outputs')
ON CONFLICT (key) DO NOTHING;

-- Richer audit log (additive, does not touch existing audit_log)
CREATE TABLE IF NOT EXISTS audit_log_v2 (
    id            BIGSERIAL     PRIMARY KEY,
    actor_user_id INTEGER,
    actor_label   VARCHAR(120),
    action        VARCHAR(100)  NOT NULL,
    target_type   VARCHAR(60)   NOT NULL,
    target_id     VARCHAR(120),
    before        JSONB,
    after         JSONB,
    source        VARCHAR(20)   NOT NULL DEFAULT 'api',
    request_id    VARCHAR(80),
    ip            VARCHAR(45),
    user_agent    TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_log_v2_target_idx
    ON audit_log_v2(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_v2_actor_idx
    ON audit_log_v2(actor_user_id, created_at DESC);
