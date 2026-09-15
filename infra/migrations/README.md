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

## Provider Feature Flags

These flags live in the `feature_flags` table (seeded by `202605170003_provider_admin_flag.sql`):

| Key                                    | Default | Purpose                                                                                                                                                                                                                                                             |
| -------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `providers.db_chain.enabled`           | `FALSE` | When `TRUE`, `src/providers/chain.py` resolves the priority chain from `provider_chains_v2` (DB-driven). When `FALSE`, the resolver falls back to environment-variable resolution only. **Flip to `TRUE` after the first credential and chain have been inserted.** |
| `providers.admin_credentials.enabled`  | `FALSE` | Allow Admin role (not just Owner) to create/update/delete/rotate credentials.                                                                                                                                                                                       |
| `providers.credentials.rotate.enabled` | `TRUE`  | Allow credential secret rotation via the dashboard. Set to `FALSE` to lock secrets in place (e.g. during an incident).                                                                                                                                              |

## Provider Backend Selection

Set `PROVIDERS_SECRET_BACKEND` in your `.env`:

| Value       | Behaviour                                                                                                         |
| ----------- | ----------------------------------------------------------------------------------------------------------------- |
| `env`       | Secrets read from environment variables (default, no DB writes).                                                  |
| `db`        | Secrets stored Fernet-encrypted in `provider_credentials.secret_blob`. Requires `PROVIDERS_FERNET_KEY` to be set. |
| `vault`     | Secrets stored in HashiCorp Vault at `vault_path`.                                                                |
| `infisical` | Secrets stored in Infisical at `vault_path`.                                                                      |

## Adding a new migration

Create a new file `2026MMDDXXXX_<short_name>.sql` after the init file.
Statements should be idempotent so re-runs are safe. Then:

```
python -m scripts.run_migrations
```
