-- AE-76: Provider Change Request & Approval Workflow
-- Creates the provider_change_requests table and supporting index.

CREATE TABLE IF NOT EXISTS provider_change_requests (
    id                  SERIAL PRIMARY KEY,
    workspace_id        INT NOT NULL,
    requested_by        INT NOT NULL REFERENCES users(id),
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_type        TEXT NOT NULL
        CHECK (request_type IN (
            'add_credential', 'change_chain_priority',
            'remove_credential', 'change_model', 'rotate_credential'
        )),
    category            TEXT NOT NULL,
    provider_name       TEXT,
    payload             JSONB NOT NULL DEFAULT '{}',
    reason              TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending_admin'
        CHECK (status IN (
            'pending_admin', 'pending_owner',
            'applied', 'rejected_by_admin', 'rejected_by_owner', 'expired'
        )),
    admin_reviewed_by   INT REFERENCES users(id),
    admin_reviewed_at   TIMESTAMPTZ,
    admin_note          TEXT,
    owner_reviewed_by   INT REFERENCES users(id),
    owner_reviewed_at   TIMESTAMPTZ,
    owner_note          TEXT,
    applied_at          TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS provider_change_requests_status_expires_idx
    ON provider_change_requests (status, expires_at);

CREATE INDEX IF NOT EXISTS provider_change_requests_workspace_idx
    ON provider_change_requests (workspace_id, status);

CREATE INDEX IF NOT EXISTS provider_change_requests_requested_by_idx
    ON provider_change_requests (requested_by);
