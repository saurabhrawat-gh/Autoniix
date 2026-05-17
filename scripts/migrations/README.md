# Migrations

Idempotent SQL migrations applied by `scripts/run_migrations.py` in
lexical order. Each file is applied at most once per database — the
runner tracks applied versions in the `schema_migrations` table by
sha256 checksum.

## Squash

`202605160050_init.sql` is the squashed union of 18 historical migration
files (versions `202605090001` through `202605160001`), collapsed on
2026-05-17. Every statement is idempotent (`IF NOT EXISTS`,
`ON CONFLICT DO NOTHING`, `OR REPLACE`), so it is safe to apply to:

- a fresh DB (creates the entire schema),
- a DB already migrated through the originals (no-op).

The pre-squash files were:

```
202605090001_foundation
202605090002_channels_v2
202605090003_providers_v2
202605090004_content_review
202605090005_auth_notifications
202605100001_channels_publish_cadence
202605110001_tenancy_hierarchy
202605110002_membership_rbac
202605110003_assets_dam
202605110004_pgvector_embeddings
202605110005_provider_routing
202605110006_review_collab
202605110008_transcoding_jobs
202605140001_providers_scope
202605140002_providers_switches
202605140003_provider_secrets
202605150001_channel_environment
202605160001_multitenant_activate
```

## Adding a new migration

Create a new file `2026MMDDXXXX_<short_name>.sql` after the init file.
Statements should be idempotent so re-runs are safe. Then:

```
python -m scripts.run_migrations
```
