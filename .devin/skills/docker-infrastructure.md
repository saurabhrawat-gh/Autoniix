# Skill: Docker Infrastructure

**Use when:** Modifying docker-compose.yml, adding/removing services, changing memory limits, debugging container issues, or working with networking/health checks.

**When NOT to use:** Application-level Python/TypeScript debugging.

---

## Service Layout (~21 containers)

### Databases

| Service           | Image                  | Port                 | Volume           |
| ----------------- | ---------------------- | -------------------- | ---------------- |
| postgres-app      | pgvector/pgvector:pg15 | 5433:5432            | pg_app_data      |
| postgres-temporal | postgres:15-alpine     | (internal)           | pg_temporal_data |
| redis             | redis:7-alpine         | 6380:6379            | redis_data       |
| minio             | minio/minio            | 9000:9000, 9001:9001 | minio_data       |

### Temporal

| Service              | Port            | Memory |
| -------------------- | --------------- | ------ |
| temporal-server      | 7233 (internal) | 512M   |
| temporal-ui          | 8080            | 128M   |
| temporal-admin-tools | —               | —      |

### Application Services

| Service   | Port | Memory | Notes                   |
| --------- | ---- | ------ | ----------------------- |
| research  | 5001 | 1.5GB  | Heavy: SBERT + pytrends |
| script    | 5002 | 512M   |                         |
| voice     | 5003 | 768M   |                         |
| assets    | 5004 | 256M   |                         |
| thumbnail | 5005 | 768M   |                         |
| assembly  | 5006 | 512M   |                         |
| delivery  | 5007 | 256M   |                         |
| analytics | 5008 | 512M   |                         |
| admin     | 5009 | 256M   |                         |
| brand     | 8012 | 256M   |                         |
| editor    | 8013 | 256M   |                         |

### Workers

| Worker            | Task Queue       | Memory |
| ----------------- | ---------------- | ------ |
| production-worker | video-production | 512M   |
| scheduler-worker  | scheduler        | 256M   |

### Dashboard

| Service       | Port | Memory |
| ------------- | ---- | ------ |
| dashboard-bff | 8020 | 256M   |
| dashboard-ui  | 3000 | 256M   |

### Remotion (separate repo)

| Service         | Port | Memory |
| --------------- | ---- | ------ |
| remotion-api    | 4000 | 512M   |
| remotion-worker | —    | 4GB    |

## Common Commands

```bash
docker compose up -d              # Start all
docker compose up -d research      # Start one service
docker compose logs -f script     # Follow logs
docker compose restart voice      # Restart service
docker compose down               # Stop all
docker compose ps                 # Status
```

## Network

All services on `yt-net` bridge network. Services communicate via Docker service names (e.g., `http://research:5001`).

## Health Checks

Most services have HTTP health checks. postgres-app: `pg_isready`, redis: `redis-cli ping`.

## Debugging

- Check logs: `docker compose logs <service>`
- Check health: `docker compose ps`
- Exec into container: `docker compose exec <service> bash`
- Check resource usage: `docker stats`
