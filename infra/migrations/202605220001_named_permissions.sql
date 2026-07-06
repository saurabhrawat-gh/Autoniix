-- Migration: 202605220001_named_permissions
-- Named permission system: 32 atomic permissions + role-permission matrix.
-- Part of Epic #13 / Story #218.

-- ── permissions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS permissions (
    name TEXT PRIMARY KEY,
    description TEXT
);

-- ── role_permissions ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS role_permissions (
    role        VARCHAR(30) NOT NULL,
    permission  TEXT        NOT NULL REFERENCES permissions(name) ON DELETE CASCADE,
    PRIMARY KEY (role, permission),
    CONSTRAINT rp_role_chk CHECK (role IN ('owner','admin','producer','editor','viewer'))
);

-- ── seed 32 permissions ────────────────────────────────────────────────────
INSERT INTO permissions (name, description) VALUES
    -- Workspace domain
    ('workspace.view',                  'View workspace and basic metadata'),
    ('workspace.settings.view',         'View workspace settings'),
    ('workspace.settings.edit',         'Edit workspace settings'),
    ('workspace.billing.view',          'View billing information'),
    ('workspace.billing.manage',        'Manage billing and subscriptions'),
    ('workspace.members.view',          'View workspace member list'),
    ('workspace.members.invite',        'Invite new members to workspace'),
    ('workspace.members.remove',        'Remove members from workspace'),
    ('workspace.members.role.change',   'Change member roles within workspace'),
    ('workspace.ownership.transfer',    'Transfer workspace ownership'),
    ('workspace.integrations.view',     'View workspace integrations'),
    ('workspace.integrations.manage',   'Manage workspace integrations'),
    ('workspace.audit_log.view',        'View workspace audit log'),
    -- Channel domain
    ('channel.view',                    'View channels'),
    ('channel.create',                  'Create new channels'),
    ('channel.settings.edit',           'Edit channel settings'),
    ('channel.delete',                  'Delete channels'),
    ('channel.credentials.view.labels', 'View credential labels on channel'),
    ('channel.credentials.manage',      'Manage channel-level credentials'),
    -- Content / Project domain
    ('project.view',                    'View projects and content'),
    ('project.create',                  'Create new projects'),
    ('project.edit',                    'Edit existing projects'),
    ('project.delete',                  'Delete projects'),
    ('project.approve',                 'Approve project content'),
    ('project.publish',                 'Publish projects'),
    -- Jobs domain
    ('job.view',                        'View pipeline jobs'),
    ('job.trigger',                     'Trigger new pipeline jobs'),
    ('job.cancel',                      'Cancel running jobs'),
    ('job.retry',                       'Retry failed jobs'),
    -- Analytics domain
    ('analytics.view',                  'View analytics dashboards'),
    ('analytics.export',                'Export analytics data'),
    -- Credentials domain
    ('credentials.view.labels',         'View credential provider labels'),
    ('credentials.view.manage',         'Manage workspace credentials')
ON CONFLICT (name) DO NOTHING;

-- ── seed role-permission matrix ────────────────────────────────────────────
-- owner: all 32
INSERT INTO role_permissions (role, permission)
SELECT 'owner', name FROM permissions
ON CONFLICT DO NOTHING;

-- admin: all except workspace.billing.manage and workspace.ownership.transfer
INSERT INTO role_permissions (role, permission)
SELECT 'admin', name FROM permissions
WHERE name NOT IN ('workspace.billing.manage','workspace.ownership.transfer')
ON CONFLICT DO NOTHING;

-- producer
INSERT INTO role_permissions (role, permission)
VALUES
    ('producer','workspace.view'),
    ('producer','workspace.settings.view'),
    ('producer','workspace.members.view'),
    ('producer','channel.view'),
    ('producer','channel.settings.edit'),
    ('producer','channel.credentials.view.labels'),
    ('producer','project.view'),
    ('producer','project.create'),
    ('producer','project.edit'),
    ('producer','project.delete'),
    ('producer','project.approve'),
    ('producer','project.publish'),
    ('producer','job.view'),
    ('producer','job.trigger'),
    ('producer','job.cancel'),
    ('producer','job.retry'),
    ('producer','analytics.view'),
    ('producer','analytics.export'),
    ('producer','credentials.view.labels')
ON CONFLICT DO NOTHING;

-- editor
INSERT INTO role_permissions (role, permission)
VALUES
    ('editor','workspace.view'),
    ('editor','channel.view'),
    ('editor','project.view'),
    ('editor','project.create'),
    ('editor','project.edit'),
    ('editor','job.view'),
    ('editor','analytics.view')
ON CONFLICT DO NOTHING;

-- viewer
INSERT INTO role_permissions (role, permission)
VALUES
    ('viewer','workspace.view'),
    ('viewer','channel.view'),
    ('viewer','project.view'),
    ('viewer','job.view'),
    ('viewer','analytics.view')
ON CONFLICT DO NOTHING;
