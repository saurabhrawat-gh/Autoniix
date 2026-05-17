# Database Migrations

## Convention

Numbered SQL files under `scripts/migrations/`. Naming:
`<YYYYMMDD><HHMM>_<slug>.sql`. Applied in lexicographic order.

All migrations must be **idempotent** — i.e. use `IF NOT EXISTS`,
`ON CONFLICT DO NOTHING`, `ON CONFLICT DO UPDATE`, or guard with
`DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$;`
so re-running the deployment script never breaks.

## Files

- `202605160050_init.sql` — base catch-up snapshot when the migrator was
  bolted on after the initial DDL existed in `init-db.sql`.
- `202605160001_multitenant_activate.sql` — adds
  `users.active_workspace_id`, `workspace_invitations.resent_at`,
  backfills workspace 1 for every existing user, sets
  `auth.multi_tenant.enabled` feature flag.
- Future migrations live alongside as new files.

## Application

Fresh deploy:
```bash
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/init-db.sql
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/seed-data.sql
# Migrations:
for f in scripts/migrations/*.sql; do
  docker compose exec -T postgres-app psql -U app -d autoniix < "$f"
done
```

Included in the `first-deploy-checklist` of `PENDING.md`.

## Rollback policy

Forward-only. There are no `down.sql` siblings. Recovery procedure:
`make backup` before any production migration; on failure `make restore`.

## Related pages

- [[Operations-Runbook]] · [[DB-Schema]]
