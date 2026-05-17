# Operations Runbook

## Purpose

Deploy, observe, recover. Long-form in `docs/OPERATIONS-RUNBOOK.md`.

## Daily operations

```bash
make up           # docker compose up -d
make down
make health       # curl all /health endpoints
make smoke        # 4-step: stack health + verify-bff + /metrics + tests
make logs s=voice # tail one service
```

## Deploy (first-time)

From `PENDING.md` first-deploy-checklist:

```bash
git pull origin main
docker compose build
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/init-db.sql
docker compose exec postgres-app psql -U app -d autoniix \
  -f /docker-entrypoint-initdb.d/seed-data.sql
make up
make health
make schedule-register   # 5 Temporal schedules
make auth-enable         # flip to v2 auth
make smoke
```

## Deploy (subsequent)

```bash
make deploy-check        # secret guards + env vars + migrations + tests
git pull && docker compose build
docker compose up -d --no-deps <changed-services>
make smoke
```

## Backup / restore

```bash
make backup              # scripts/backup.sh
make restore F=<file>    # full DB + MinIO restore
```

`backup-restore-drill` should be done monthly per `PENDING.md`.

## Emergency stop

Two paths:

1. **Dashboard** — Settings → Emergency stop. Sets `system_config.emergency_stop=TRUE`.
2. **CLI** — `psql ... UPDATE system_config SET config_value='TRUE' WHERE
   config_key='emergency_stop'`.

Both: running workflows check on their next `check_system_status` and bail.

## Common incidents

| Symptom | Action |
|---|---|
| YouTube upload 403 | Refresh OAuth token, verify `yt-analytics.readonly` scope |
| All renders failing | Check `remotion-worker` memory + tmp disk space |
| Budget exceeded warnings | Inspect Grafana Budget dashboard, halve `max_cost_usd` per channel |
| db_pool.pressure > 0.7 | Surface `postgres-read-replicas` from PENDING.md |
| Temporal queue depth growing | Add a second `worker-production` replica |

## Watch windows after deploy

| Window | Watch |
|---|---|
| Week 1 | Calibrate alert rules vs observed baselines |
| Days 7–30 | Diversity Floor panel — 0% may be too loose, > 25% too aggressive |
| Days 7–14 | Prediction Calibration panel populates; Brier < 0.20 = healthy |
| Week 2+ | Per-niche `weighted_fraction` rising from 0% → 30–60% |

## Related pages

- [[Operations-VPS-Bootstrap]] · [[Observability-Alerts]] · [[CI-CD]]
