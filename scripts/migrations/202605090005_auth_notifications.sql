-- 202605090005_auth_notifications.sql
-- Phase 4 (S7 + S4 + S8): Real auth + notification center.

-- Users
CREATE TABLE IF NOT EXISTS users (
    id                BIGSERIAL    PRIMARY KEY,
    email             VARCHAR(255) UNIQUE NOT NULL,
    display_name      VARCHAR(120),
    password_hash     TEXT,
    role              VARCHAR(20)  NOT NULL DEFAULT 'viewer',
    mfa_secret        TEXT,
    mfa_enabled       BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verified    BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verify_token TEXT,
    oauth_providers   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    last_login_at     TIMESTAMPTZ,
    disabled          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT users_role_chk CHECK (role IN ('owner','admin','editor','reviewer','viewer'))
);
CREATE INDEX IF NOT EXISTS users_email_idx ON users(lower(email));

CREATE TABLE IF NOT EXISTS sessions (
    id                  BIGSERIAL    PRIMARY KEY,
    user_id             BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  TEXT         NOT NULL UNIQUE,
    device              TEXT,
    ip                  VARCHAR(45),
    user_agent          TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ  NOT NULL,
    revoked_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS password_resets (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT         NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ  NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id            BIGSERIAL    PRIMARY KEY,
    event_type    VARCHAR(80)  NOT NULL,
    severity      VARCHAR(20)  NOT NULL DEFAULT 'info',
    title         TEXT         NOT NULL,
    body          TEXT,
    payload       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    channel_id    VARCHAR(20),
    video_id      VARCHAR(100),
    dedupe_key    VARCHAR(120),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    read_by       BIGINT[]     NOT NULL DEFAULT '{}',
    CONSTRAINT notifications_severity_chk CHECK (severity IN ('info','warn','error','critical'))
);
CREATE INDEX IF NOT EXISTS notifications_recent_idx ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS notifications_dedupe_idx ON notifications(dedupe_key, created_at DESC)
    WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS notifications_event_idx ON notifications(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_routes (
    id              BIGSERIAL    PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    event_pattern   VARCHAR(120) NOT NULL,  -- supports '*' wildcards
    severity_min    VARCHAR(20)  NOT NULL DEFAULT 'info',
    channels        TEXT[]       NOT NULL,  -- ['slack','email','browser','webhook']
    filter          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    config          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id              BIGSERIAL    PRIMARY KEY,
    notification_id BIGINT       NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    route_id        BIGINT       REFERENCES notification_routes(id) ON DELETE SET NULL,
    channel         VARCHAR(40)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'queued',
    attempts        SMALLINT     NOT NULL DEFAULT 0,
    response        JSONB,
    error           TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT deliveries_status_chk CHECK (status IN ('queued','sent','failed','dropped'))
);
CREATE INDEX IF NOT EXISTS deliveries_notification_idx
    ON notification_deliveries(notification_id);
CREATE INDEX IF NOT EXISTS deliveries_status_idx
    ON notification_deliveries(status, created_at DESC);

-- Default routes (disabled until user configures Slack/email)
INSERT INTO notification_routes (name, event_pattern, severity_min, channels, enabled) VALUES
    ('Critical to Slack',     '*',                 'critical', ARRAY['slack'],   FALSE),
    ('Errors to Slack',       'pipeline.*',        'error',    ARRAY['slack'],   FALSE),
    ('Review pending',        'review.pending',    'info',     ARRAY['browser'], TRUE),
    ('Job complete',          'video.complete',    'info',     ARRAY['browser'], TRUE),
    ('Provider failure',      'provider.failed',   'warn',     ARRAY['slack'],   FALSE)
ON CONFLICT DO NOTHING;
