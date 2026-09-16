-- Migration 202605170003: Provider admin-credential feature flag
-- Inserts the feature flag that gates Admin access to credential CRUD.
-- Default OFF: only Owner can create/update/delete/rotate credentials.
-- Flip ON in the dashboard to also allow Admin.

INSERT INTO feature_flags (key, enabled, description)
VALUES (
    'providers.admin_credentials.enabled',
    FALSE,
    'Allow Admin role to create, update, delete and rotate provider credentials (Owner-only by default)'
)
ON CONFLICT (key) DO NOTHING;

INSERT INTO feature_flags (key, enabled, description)
VALUES (
    'providers.credentials.rotate.enabled',
    TRUE,
    'Allow credential secret rotation via the dashboard (disable to lock secrets in place)'
)
ON CONFLICT (key) DO NOTHING;
