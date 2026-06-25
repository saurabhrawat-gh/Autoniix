-- IM-182: Workspace deletion email notification idempotency log
-- Tracks which email events have already been sent for a workspace so that
-- retries and cron re-runs never double-send.
CREATE TABLE IF NOT EXISTS workspace_deletion_notifications (
    id             BIGSERIAL    PRIMARY KEY,
    workspace_id   BIGINT       NOT NULL,
    event_type     VARCHAR(50)  NOT NULL,  -- soft_delete | warning_48h | cancelled | hard_deleted
    sent_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT workspace_deletion_notifications_unique
        UNIQUE (workspace_id, event_type)
);

CREATE INDEX IF NOT EXISTS wdn_workspace_id_idx
    ON workspace_deletion_notifications (workspace_id);
