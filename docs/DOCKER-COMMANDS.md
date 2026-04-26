# Docker Compose Commands Reference

> Quick reference for managing the yt-automation stack.

---

## Full Stack

```bash
# Start everything
docker compose up -d

# Stop everything (containers removed, volumes preserved)
docker compose down

# Stop everything + delete volumes (⚠️ wipes DB data)
docker compose down -v

# Rebuild all images + start
docker compose up -d --build
```

---

## Individual Service

```bash
# Start one service (+ its dependencies)
docker compose up -d <service>

# Stop one service
docker compose stop <service>

# Restart one service
docker compose restart <service>

# Rebuild + restart one service (after code changes)
docker compose up -d --build <service>

# View logs (live, last 50 lines)
docker compose logs -f <service> --tail 50

# Check status
docker compose ps <service>
```

---

## Multiple Services

```bash
# Start a few
docker compose up -d script voice direction

# Stop a few
docker compose stop remotion-api remotion-worker

# Rebuild + restart changed services
docker compose up -d --build script voice thumbnail direction assembly
```

---

## Scaling

```bash
# Run 3 parallel Remotion render workers
docker compose up -d --scale remotion-worker=3

# Scale back to 1
docker compose up -d --scale remotion-worker=1

# Run 2 Temporal production workers
docker compose up -d --scale worker-production=2
```

---

## Debugging

```bash
# Shell into a running container
docker compose exec <service> sh

# Check container resource usage
docker stats

# Inspect a container
docker compose inspect <service>

# View all container statuses
docker compose ps -a

# Force recreate a stuck container
docker compose up -d --force-recreate <service>
```

---

## Database

```bash
# Connect to app database
docker compose exec postgres-app psql -U app -d yt_automation

# Run seed data
docker compose exec postgres-app psql -U app -d yt_automation -f /dev/stdin < scripts/seed-data.sql

# Backup database
docker compose exec postgres-app pg_dump -U app yt_automation > backup.sql
```

---

## Service Names

| Service            | Compose Name         | Port  |
|--------------------|----------------------|-------|
| Research           | `research`           | 8001  |
| Script             | `script`             | 8002  |
| Voice              | `voice`              | 8003  |
| Assets             | `assets`             | 8004  |
| Thumbnail          | `thumbnail`          | 8005  |
| Assembly           | `assembly`           | 8006  |
| Delivery           | `delivery`           | 8007  |
| Analytics          | `analytics`          | 8008  |
| Admin              | `admin`              | 8009  |
| Direction          | `direction`          | 8010  |
| Sheets Sync        | `sheets-sync`        | 8011  |
| Remotion API       | `remotion-api`       | 4000  |
| Remotion Worker    | `remotion-worker`    | —     |
| Temporal Server    | `temporal`           | 7233  |
| Temporal UI        | `temporal-ui`        | 8080  |
| Production Worker  | `worker-production`  | —     |
| Scheduler Worker   | `worker-scheduler`   | —     |
| Postgres (App)     | `postgres-app`       | 5433  |
| Postgres (Temporal)| `postgres-temporal`  | —     |
| Redis              | `redis`              | 6380  |
| MinIO              | `minio`              | 9000/9001 |

---

## Common Workflows

### After code changes to a Python service
```bash
docker compose up -d --build script   # or voice, direction, etc.
```

### After code changes to Remotion
```bash
docker compose up -d --build remotion-api remotion-worker
```

### After updating seed-data.sql
```bash
docker compose exec postgres-app psql -U app -d yt_automation -f /dev/stdin < scripts/seed-data.sql
```

### After updating Temporal workflow code
```bash
docker compose up -d --build worker-production worker-scheduler
```

### Full rebuild (nuclear option)
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```
