# Infrastructure & Self-Host Runbook

> Docker Compose for the full stack. Sizing guide. Backup strategy. Monitoring. Scaling playbook.

---

## Docker Compose (Full Stack)

```yaml
version: "3.8"

# ─── Networks ────────────────────────────────────────────
networks:
  yt-net:
    driver: bridge
  yt-internal:
    driver: bridge
    internal: true

# ─── Volumes ─────────────────────────────────────────────
volumes:
  pg_app_data:
  pg_temporal_data:
  redis_data:
  minio_data:
  temporal_data:
  traefik_letsencrypt:

# ─── Services ────────────────────────────────────────────
services:

  # ── API Gateway ──────────────────────────────────────
  traefik:
    image: traefik:v3.0
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_letsencrypt:/letsencrypt
    networks: [yt-net]
    restart: always

  # ── Temporal Server ──────────────────────────────────
  temporal:
    image: temporalio/auto-setup:latest
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=${TEMPORAL_DB_PASSWORD}
      - POSTGRES_SEEDS=postgres-temporal
      - DYNAMIC_CONFIG_FILE_PATH=config/dynamicconfig/production.yaml
    depends_on:
      postgres-temporal:
        condition: service_healthy
    networks: [yt-net, yt-internal]
    restart: always
    deploy:
      resources:
        limits:
          memory: 2G

  temporal-ui:
    image: temporalio/ui:latest
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - TEMPORAL_CORS_ORIGINS=https://${DOMAIN}
    depends_on: [temporal]
    networks: [yt-net]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.temporal-ui.rule=Host(`temporal.${DOMAIN}`)"
      - "traefik.http.routers.temporal-ui.tls.certresolver=letsencrypt"
      - "traefik.http.routers.temporal-ui.middlewares=temporal-auth"
      - "traefik.http.middlewares.temporal-auth.basicauth.users=${TEMPORAL_UI_AUTH}"
    restart: always

  temporal-admin-tools:
    image: temporalio/admin-tools:latest
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
    depends_on: [temporal]
    networks: [yt-internal]

  # ── Databases ────────────────────────────────────────
  postgres-app:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: yt_automation
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_app_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/01-init.sql
    networks: [yt-internal]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d yt_automation"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G

  postgres-temporal:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: temporal
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: ${TEMPORAL_DB_PASSWORD}
    volumes:
      - pg_temporal_data:/var/lib/postgresql/data
    networks: [yt-internal]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal -d temporal"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks: [yt-internal]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY}
    volumes:
      - minio_data:/data
    networks: [yt-internal]
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always

  # ── Application Services ─────────────────────────────
  research:
    build: ./services/research
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, postgres-app]
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M

  script:
    build: ./services/script
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, postgres-app]
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M

  voice:
    build: ./services/voice
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, minio]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  assets:
    build: ./services/assets
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, minio]
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M

  thumbnail:
    build: ./services/thumbnail
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, minio]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  assembly:
    build: ./services/assembly
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, postgres-app, minio]
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M

  delivery:
    build: ./services/delivery
    env_file: .env
    networks: [yt-internal]
    depends_on: [postgres-app, minio]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  analytics:
    build: ./services/analytics
    env_file: .env
    networks: [yt-internal]
    depends_on: [redis, postgres-app]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  admin:
    build: ./services/admin
    env_file: .env
    networks: [yt-net, yt-internal]
    depends_on: [postgres-app]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.admin.rule=Host(`api.${DOMAIN}`)"
      - "traefik.http.routers.admin.tls.certresolver=letsencrypt"
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  # ── Temporal Workers ─────────────────────────────────
  worker-production:
    build: ./workers
    command: python -m workers.production
    env_file: .env
    environment:
      - TEMPORAL_HOST=temporal:7233
    networks: [yt-internal]
    depends_on: [temporal, research, script, voice, assets, thumbnail, assembly]
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M

  worker-scheduler:
    build: ./workers
    command: python -m workers.scheduler
    env_file: .env
    environment:
      - TEMPORAL_HOST=temporal:7233
    networks: [yt-internal]
    depends_on: [temporal, postgres-app]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  worker-analytics:
    build: ./workers
    command: python -m workers.analytics
    env_file: .env
    environment:
      - TEMPORAL_HOST=temporal:7233
    networks: [yt-internal]
    depends_on: [temporal, analytics]
    restart: always
    deploy:
      resources:
        limits:
          memory: 256M

  # ── Remotion (optional, same VPS for small scale) ────
  # For dedicated VPS, run yt-automation-remotion's own docker-compose
  # remotion:
  #   image: ghcr.io/your-org/yt-automation-remotion:latest
  #   env_file: .env
  #   networks: [yt-internal]
  #   depends_on: [redis, minio]
  #   deploy:
  #     resources:
  #       limits:
  #         memory: 4G
  #         cpus: "4"
```

---

## Environment Variables Reference

```bash
# ── Domain & Gateway ───────────────────────────────────
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
TEMPORAL_UI_AUTH=admin:$$apr1$$...  # htpasswd format

# ── Databases ──────────────────────────────────────────
DB_PASSWORD=<strong-random-64-chars>
TEMPORAL_DB_PASSWORD=<strong-random-64-chars>
DATABASE_URL=postgresql://app:${DB_PASSWORD}@postgres-app:5432/yt_automation
REDIS_URL=redis://redis:6379

# ── Object Storage (MinIO) ────────────────────────────
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=<20-char-key>
S3_SECRET_KEY=<40-char-secret>
S3_BUCKET=yt-automation
S3_PUBLIC_BASE_URL=https://s3.${DOMAIN}/yt-automation
S3_FORCE_PATH_STYLE=true

# ── AI Providers ───────────────────────────────────────
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=AIza...

# ── TTS ────────────────────────────────────────────────
FISH_AUDIO_API_KEY=...
TTS_PROVIDER=fish_audio  # Swappable: fish_audio | elevenlabs | google_tts

# ── Search ─────────────────────────────────────────────
SERPAPI_KEY=...
SEARCH_PROVIDER=serpapi  # Swappable: serpapi | google_custom

# ── Image ──────────────────────────────────────────────
PIXABAY_API_KEY=...
IMAGE_PROVIDER=dalle  # Swappable: dalle | stock_only

# ── YouTube ────────────────────────────────────────────
YOUTUBE_API_KEY=AIza...
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...

# ── Admin ──────────────────────────────────────────────
ADMIN_JWT_SECRET=<64-char-random>

# ── Temporal ───────────────────────────────────────────
TEMPORAL_HOST=temporal:7233
TEMPORAL_NAMESPACE=default

# ── Remotion (if separate VPS) ─────────────────────────
REMOTION_BASE_URL=http://remotion:4000
# Or for separate VPS: http://10.0.0.2:4000
```

---

## Sizing Guide

### Memory Budget (CX31: 8GB total)

| Component | Memory Limit | Notes |
|-----------|-------------|-------|
| Temporal Server | 2 GB | Includes frontend, history, matching, worker |
| PostgreSQL (app) | 1 GB | Shared buffers, work_mem |
| PostgreSQL (temporal) | 512 MB | Lightweight |
| Redis | 512 MB | maxmemory with LRU eviction |
| MinIO | 256 MB | Minimal for metadata |
| 8 Python services | 256 MB each = 2 GB | FastAPI + uvicorn |
| 3 Temporal workers | 256-512 MB each = 1 GB | Polling + activity execution |
| Traefik | 128 MB | Lightweight |
| **Total** | **~7.5 GB** | Fits CX31 for 1-3 channels |

### VPS Tiers

| Channels | Main VPS | DB VPS | Render VPS | Total Infra |
|----------|---------|--------|-----------|-------------|
| 1-3 | CX31 ($18) all-in-one | — | — | $18 |
| 5 | CX31 ($18) | — | CX21 ($7) | $25 |
| 10 | CX31 ($18) | CX21 ($7) | CX31 ($24) | $49 |
| 25 | CX41 ($36) | CX31 ($18) | 2× CX31 ($48) | $102 |
| 50 | CX51 ($61) | CX41 ($36) | 3× CX31 ($72) | $169 |
| 100 | 3× CX41 ($108) | CX51+CX31 ($79) | 4× CX31 ($96) + misc ($17) | $300 |

---

## Backup Strategy

### PostgreSQL (Daily)

```bash
#!/bin/bash
# scripts/backup.sh — run via cron at 3 AM
DATE=$(date +%Y%m%d)

# App database
docker exec postgres-app pg_dump -U app yt_automation | gzip > /backups/pg_app_${DATE}.sql.gz

# Temporal database
docker exec postgres-temporal pg_dump -U temporal temporal | gzip > /backups/pg_temporal_${DATE}.sql.gz

# Upload to MinIO backup bucket
mc cp /backups/pg_app_${DATE}.sql.gz minio/yt-automation/backups/${DATE}/
mc cp /backups/pg_temporal_${DATE}.sql.gz minio/yt-automation/backups/${DATE}/

# Retain 30 days locally
find /backups -name "*.sql.gz" -mtime +30 -delete
```

Crontab:
```
0 3 * * * /opt/yt-automation/scripts/backup.sh >> /var/log/backup.log 2>&1
```

### MinIO (Versioning)

```bash
# Enable versioning on the bucket
mc version enable minio/yt-automation
```

All objects retain previous versions. To recover a deleted file:
```bash
mc ls --versions minio/yt-automation/scripts/BS001/VID_.../
mc cp --version-id <id> minio/yt-automation/scripts/BS001/VID_.../ ./recovered/
```

### Weekly Full Snapshot

```bash
# VPS snapshot via Hetzner API (or console)
# Cost: ~20% of VPS price for snapshot storage
hcloud server create-image --type snapshot --description "weekly-$(date +%Y%m%d)" <server-id>
```

---

## Monitoring

### Phase 1: Basics (Day 1)

- **Temporal Web UI** (`temporal.yourdomain.com`): Workflow history, failures, retries
- **Docker health checks**: All services have health checks; Docker restarts unhealthy containers
- **Structured logging**: JSON logs from all services to stdout → Docker log driver

```python
# Structured logging setup (every service)
import structlog
logger = structlog.get_logger()

logger.info("voice_generated", scene_id="s1", duration_s=8.2, cost_usd=0.17, provider="fish_audio")
```

### Phase 2: Prometheus + Grafana (Week 8+)

```yaml
# Add to docker-compose.yml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
    networks: [yt-internal]

  grafana:
    image: grafana/grafana:latest
    networks: [yt-net]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`grafana.${DOMAIN}`)"
      - "traefik.http.routers.grafana.tls.certresolver=letsencrypt"
```

Dashboards:
- Videos produced per day/channel
- API cost per day/provider
- Error rate per service
- Render queue depth
- Budget utilization
- Quality score distribution

### Alerts

| Alert | Condition | Action |
|-------|-----------|--------|
| Service down | Health check fails 3× | Restart + notify |
| High error rate | >20% errors in 10 min | Notify + check circuit breakers |
| Budget 80% | Daily spend ≥ 80% of limit | Notify |
| Disk space low | <10% free | Notify + cleanup old renders |
| Render queue backed up | >5 pending renders | Notify + consider scaling |
| Workflow failure spike | >3 failures in 1 hour | Notify + check Temporal UI |

---

## Scaling Playbook

### When to Scale

| Signal | Action |
|--------|--------|
| VPS CPU consistently >80% | Upgrade VPS tier or split services |
| VPS memory consistently >85% | Upgrade VPS tier or split DB |
| Render queue >5 pending | Add render VPS |
| DB query latency >100ms | Move DB to dedicated VPS |
| Redis memory >80% | Reduce TTLs or upgrade |

### How to Split (5+ channels)

1. **Separate Remotion**: Move to dedicated VPS, connect via VPN
2. **Separate DB**: Move PostgreSQL + Redis + MinIO to dedicated VPS
3. **Scale renders**: Add more render VPS instances behind a round-robin

### Docker Compose → Kubernetes (Roadmap, 50+ channels)

When Docker Compose reaches its limits:
1. Convert services to Helm charts
2. Deploy to managed Kubernetes (Hetzner Cloud K8s or self-managed)
3. Use horizontal pod autoscaling for services and render workers
4. Use PersistentVolumeClaims for DB and MinIO
5. Temporal can run as a Helm chart (`temporalio/helm-charts`)

This migration preserves all service contracts — services don't know they moved from Docker Compose to K8s.
