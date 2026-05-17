# Architecture: Data Layer

## Purpose

Four storage tiers persist all stateful data: PostgreSQL (relational +
vector), Redis (cache + rate limits + BullMQ queue), MinIO (object storage),
and a separate PostgreSQL instance for Temporal's own state.

## Source files

- `docker-compose.yml` — `postgres-app`, `postgres-temporal`, `redis`, `minio`, `minio-bootstrap`
- `src/db.py` — asyncpg connection pool
- `src/redis_client.py` — Redis client
- `src/providers/storage/minio_provider.py` — MinIO wrapper with prefixing
- `scripts/init-db.sql` — schema DDL
- `scripts/seed-data.sql` — system_config + prompt_registry seeds
- `scripts/migrations/` — numbered migrations

## PostgreSQL (postgres-app)

- **Image:** `pgvector/pgvector:pg15`
- **Port:** host `5433` → container `5432`
- **DB / user:** `${DB_NAME:-autoniix}` / `${DB_USER:-app}`
- **Init:** `init-db.sql` then `seed-data.sql` mounted via `docker-entrypoint-initdb.d`.
- **Extensions:** `pgvector` for SBERT embeddings (research similarity).
- **Pool** (`src/config.py:90-98`): asyncpg, `min=2`, `max=10` per process,
  `statement_timeout=30_000 ms`, `acquire_timeout=10s`.

Key table groups (full DDL in [[DB-Schema]]):

- **Core:** `channels`, `videos`, `job_events`, `audit_log`, `system_config`,
  `prompt_registry`.
- **Auth / multi-tenant:** `users`, `workspaces`, `workspace_members`,
  `workspace_invitations`.
- **Research intelligence:** `competitor_channels`, `competitor_videos`,
  `trend_signals`, `topic_embeddings` (vector), `research_features`,
  `performance_outcomes`, `ml_models`, `bandit_state`, `phrase_bank`.
- **Script intelligence:** `script_features`, `script_outcomes`,
  `script_models`, `script_bandit_state`.
- **Experiments:** `experiments`, `experiment_assignments`,
  `experiment_outcomes`, `intelligence_metrics`, `model_health`.

## PostgreSQL (postgres-temporal)

- **Image:** `postgres:15-alpine`
- **Port:** host `5434` → container `5432`
- Holds Temporal server's own history / visibility tables. Auto-provisioned
  by `temporalio/auto-setup` on first boot.

## Redis

- **Image:** `redis:7-alpine`
- **Port:** host `6380` → container `6379`
- **Eviction:** `--maxmemory 512mb --maxmemory-policy allkeys-lru`
- **Uses:**
  - API response cache (research trends, competitor lookups)
  - Dedup hashes (SimHash 64-bit)
  - Rate limits (slowapi backing store)
  - BullMQ render queue (Remotion API → worker)
  - Pub/sub for in-app notifications
  - Optional Infisical store (`db /3`)

## MinIO

- **Image:** `minio/minio:latest`
- **Ports:** S3 `9000`, console `9001`
- **Bucket:** `${S3_BUCKET:-autoniix}` (auto-created by `minio-bootstrap`).
- **Layout** (key prefix from `src/environment.py:122-124`):

```
s3://autoniix/
  prod/      ← production renders, voiceovers, thumbnails
  test/      ← all test-mode artefacts
  public/    ← publicly readable (thumbnails fetched by YouTube)
```

The `minio-bootstrap` container applies a public-read anonymous policy on
the `public/*` prefix only, while keeping everything else private and
presigned.

## Volumes

| Volume | Holds |
|---|---|
| `pg_app_data` | App Postgres data |
| `pg_temporal_data` | Temporal Postgres data |
| `redis_data` | Redis AOF/RDB |
| `minio_data` | All objects |
| `remotion_tmp` | Per-render scratch |
| `remotion_bundle_cache` | Webpack bundle cache for tiered workers |
| `prometheus_data` / `grafana_data` / `loki_data` | Observability TSDB / dashboards / logs |
| `letsencrypt_data` | ACME certs (TLS profile) |

## Backups

`scripts/backup.sh` dumps Postgres + MinIO to `/mnt/backups`, then optionally
uploads offsite. `make backup` / `make restore` wrap it.

## Related pages

- [[DB-Schema]]
- [[DB-Migrations]]
- [[Providers-Storage]]
- [[Operations-Runbook]]
