-- 202605110002_membership_rbac.sql
-- Wave 1: Multi-user RBAC with scoped role bindings.
-- Depends on: users table (202605090005), workspaces + brands (202605110001).

-- Workspace memberships
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id    BIGINT          NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         BIGINT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(30)     NOT NULL DEFAULT 'viewer',
    invited_by      BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    joined_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id),
    CONSTRAINT wm_role_chk CHECK (role IN
        ('owner','admin','producer','editor','reviewer','analyst','viewer'))
);
CREATE INDEX IF NOT EXISTS workspace_members_user_idx ON workspace_members(user_id);

-- Backfill existing users into the default workspace
INSERT INTO workspace_members (workspace_id, user_id, role)
SELECT 1, id,
       CASE WHEN role IN ('owner','admin','editor','reviewer','viewer') THEN role ELSE 'viewer' END
FROM users
ON CONFLICT (workspace_id, user_id) DO NOTHING;

-- Fine-grained role bindings (scope-level)
CREATE TABLE IF NOT EXISTS role_bindings (
    id          BIGSERIAL       PRIMARY KEY,
    user_id     BIGINT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope       VARCHAR(30)     NOT NULL,
    scope_id    VARCHAR(40)     NOT NULL,
    role        VARCHAR(30)     NOT NULL,
    granted_by  BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, scope, scope_id),
    CONSTRAINT rb_scope_chk CHECK (scope IN
        ('global','workspace','brand','channel')),
    CONSTRAINT rb_role_chk CHECK (role IN
        ('owner','admin','producer','editor','reviewer','analyst','viewer','external_reviewer'))
);
CREATE INDEX IF NOT EXISTS role_bindings_user_idx  ON role_bindings(user_id, scope);
CREATE INDEX IF NOT EXISTS role_bindings_scope_idx ON role_bindings(scope, scope_id);

-- Workspace invitations
CREATE TABLE IF NOT EXISTS workspace_invitations (
    id              BIGSERIAL       PRIMARY KEY,
    workspace_id    BIGINT          NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email           VARCHAR(255)    NOT NULL,
    role            VARCHAR(30)     NOT NULL DEFAULT 'viewer',
    token_hash      TEXT            NOT NULL UNIQUE,
    invited_by      BIGINT          REFERENCES users(id) ON DELETE SET NULL,
    accepted_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS workspace_invitations_ws_idx ON workspace_invitations(workspace_id, accepted_at);

-- Permission check helper view
-- Returns the effective role for (user, scope, scope_id).
-- Resolution: global → workspace → brand → channel (most specific wins).
-- Used by application code via SELECT * FROM effective_role WHERE ...
CREATE OR REPLACE VIEW effective_roles AS
SELECT
    rb.user_id,
    rb.scope,
    rb.scope_id,
    rb.role,
    CASE rb.scope
        WHEN 'global'    THEN 1
        WHEN 'workspace' THEN 2
        WHEN 'brand'     THEN 3
        WHEN 'channel'   THEN 4
    END AS specificity
FROM role_bindings rb
WHERE (rb.expires_at IS NULL OR rb.expires_at > NOW());

-- Feature flags for RBAC enforcement
INSERT INTO feature_flags (key, enabled, description) VALUES
    ('auth.rbac.enabled',        FALSE, 'Enforce fine-grained RBAC; when disabled, all authenticated users are treated as owner'),
    ('auth.invitations.enabled', FALSE, 'Enable workspace invitation flow')
ON CONFLICT (key) DO NOTHING;
