# Architecture: Container Topology

## Purpose

Complete inventory of every container in the compose stack: image, port,
memory limit, dependencies and role.

## Source

- `docker-compose.yml` (entire file)

## Service table

### Databases / queue / object store

| Service | Image | Memory | Notes |
|---|---|---|---|
| `postgres-app` | `pgvector/pgvector:pg15` | (host) | App DB + pgvector |
| `postgres-temporal` | `postgres:15-alpine` | (host) | Temporal’s own DB |
| `redis` | `redis:7-alpine` | 512MB cap | Cache + BullMQ |
| `minio` | `minio/minio:latest` | (host) | Object storage |
| `minio-bootstrap` | `minio/mc:latest` | one-shot | Creates bucket + public policy |
| `infisical` (profile `secrets`) | `infisical/infisical:latest-postgres` | 512M | Optional secrets store |

### Temporal

| Service | Image | Memory | Notes |
|---|---|---|---|
| `temporal` | `temporalio/auto-setup:latest` | — | Frontend on 7233 |
| `temporal-ui` | `temporalio/ui:latest` | — | Web UI on 8080 |

### Application services (FastAPI)

| Service | Port | Memory | Role |
|---|---|---|---|
| `research` | 8001 | 1536M | Trend / competitor / opportunity intelligence |
| `script` | 8002 | 1536M | 13-step script pipeline |
| `voice` | 8003 | 768M | TTS + prosody intelligence |
| `assets` | 8004 | 512M | Stock footage + DALL·E fallback |
| `thumbnail` | 8005 | 768M | DALL·E + Vision QC |
| `assembly` | 8006 | 512M | Pre-render validation |
| `delivery` | 8007 | 256M | YouTube upload + SEO |
| `analytics` | 8008 | 512M | Analytics + pattern mining |
| `admin` | 8009 | 256M | CRUD endpoints |
| `direction` | 8010 | 512M | Per-segment direction v3 |
| `sheets-sync` | 8011 | 256M | Google Sheets sync |
| `brand` | 8012 | 512M | Brand DNA |
| `editor` | 8013 | 512M | Post-production |
| `dashboard-bff` | 8020 | 256M | BFF API |
| `dashboard-ui` | 3000 | 256M | Next.js admin UI |

### Render engine (Remotion)

| Service | Memory | Profile | Role |
|---|---|---|---|
| `remotion-api` | 2G | (default) | Express API + BullMQ producer |
| `remotion-worker` | 4G | (default) | Default Chromium renderer |
| `remotion-worker-tier1` | 4G | `vision` | Creative-heavy renders |
| `remotion-worker-tier2` | 2G | `vision` | Volume renders |
| `remotion-worker-concat` | 1G | `vision` | Final concat |
| `remotion-mcp` | 512M | `vision` | MCP server on 4100 |

### Workers

| Service | Memory | Task queue |
|---|---|---|
| `worker-production` | 512M | `video-production` |
| `worker-scheduler` | 256M | `scheduler` |

### Observability

| Service | Memory | Notes |
|---|---|---|
| `prometheus` | 512M | 15d retention |
| `alertmanager` | 128M | 12 rules → Slack |
| `node-exporter` | 64M | Host metrics |
| `loki` | 384M | 30d log retention |
| `promtail` | 128M | Tails Docker logs |
| `grafana` | 256M | Provisioned dashboards |
| `traefik` (profile `tls`) | 128M | TLS gateway |

Approx container count:
- Default: ~21 containers
- With `tls`: +1 (traefik)
- With `vision`: +4 (tier1, tier2, concat, mcp)
- With `secrets`: +1 (infisical)

## Healthchecks

All long-running services expose `/health`. Compose `depends_on:
{ condition: service_healthy }` is used wherever a startup ordering matters
(e.g. `dashboard-bff` waits on `postgres-app` healthy, `worker-production`
waits on Temporal + Postgres + Redis healthy).

## Related pages

- [[Architecture-Network-And-Gateway]]
- [[Architecture-Data-Layer]]
- [[Operations-Runbook]]
