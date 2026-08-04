# Phase 5 Migration: Go → Python Notification Dispatcher

**Status:** ✅ Complete  
**Date:** 2026-08-04  
**Duration:** ~2 hours (well under the 5–7 day estimate)

---

## Summary

The Go notification-dispatcher (G1 service) has been ported to Python and deployed alongside the legacy Go service. Both poll the same `notification_deliveries` table using `FOR UPDATE SKIP LOCKED` to avoid collisions, enabling a gradual cutover.

---

## What Landed

### Service: notification-dispatcher-v2

| Component | Lines | Description |
|-----------|-------|-------------|
| `main.py` | 130 | FastAPI app with lifecycle management |
| `dispatcher.py` | 175 | Polling loop + claim/deliver logic |
| `channels.py` | 130 | Slack, Webhook, Browser, Email channels |
| `config.py` | 20 | Pydantic settings |
| `Dockerfile` | 25 | Multi-stage build with healthcheck |
| `README.md` | 200 | Architecture, config, cutover plan |

**Total:** ~680 lines (Go: ~400 lines across 3 files)

---

## Key Differences from Go

### 1. Parallel Delivery

**Go:**
```go
for _, r := range rows {
    d.deliver(ctx, r)  // sequential
}
```

**Python:**
```python
await asyncio.gather(*[self._deliver(r) for r in rows], return_exceptions=True)
```

### 2. HTTP Client

**Go:** `http.Client` with per-request timeout  
**Python:** `httpx.AsyncClient` with global timeout + connection pooling (100 max, 20 keepalive)

### 3. Database Driver

**Go:** `pgx/v5` with `pgxpool.Pool`  
**Python:** `asyncpg` with `asyncpg.Pool`

### 4. Logging

**Go:** `zap.SugaredLogger`  
**Python:** `structlog` with JSON output

---

## Architecture

### Channels

| Channel | Description | Config |
|---------|-------------|--------|
| `slack` | Posts to Slack Incoming Webhook with color-coded attachments | `webhook_url` or `SLACK_WEBHOOK_URL` env |
| `webhook` | POSTs raw notification JSON to configured URL | `url` in route config |
| `browser` | No-op (served by notification center UI) | N/A |
| `email` | Placeholder (always fails until SMTP wired) | N/A |

### Polling Loop

1. Every `POLL_INTERVAL_MS` (default 15s), wake up
2. Claim up to `BATCH_SIZE` (default 50) stale rows using `FOR UPDATE SKIP LOCKED`
3. For each row, invoke channel's `send()` method with `HTTP_TIMEOUT_MS` (default 10s)
4. On success: mark `status='sent'`, record response
5. On failure: mark `status='failed'`, record error
6. Rows with `attempts >= MAX_ATTEMPTS` are left in `status='failed'` permanently

**Stale criteria:**
- `status='queued'` AND `created_at < NOW() - STALE_AFTER_MS`, OR
- `status='failed'` AND `attempts < MAX_ATTEMPTS` AND `created_at < NOW() - STALE_AFTER_MS`

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | `postgresql://app:...@postgres-app:5432/autoniix` | App database connection string |
| `HTTP_ADDR` | `0.0.0.0:8090` | Health/ready endpoint listen address |
| `POLL_INTERVAL_MS` | `15000` | How often to poll for work (ms) |
| `STALE_AFTER_MS` | `60000` | Min age before claiming a row (ms) |
| `BATCH_SIZE` | `50` | Max rows claimed per tick |
| `MAX_ATTEMPTS` | `3` | Total delivery attempts before permanent failure |
| `HTTP_TIMEOUT_MS` | `10000` | Timeout for each channel HTTP call (ms) |
| `SLACK_WEBHOOK_URL` | `""` | Fallback Slack webhook if route config has none |

---

## Cutover Plan

### Current State
- **Go dispatcher:** `services/notification-dispatcher/` (port 8090, profiles: go-services)
- **Python dispatcher:** `services/notification-dispatcher-v2/` (port 8091)
- Both run side-by-side

### Rollout Steps

1. **Deploy Python dispatcher** (this phase)
   ```bash
   make ndisp2-up
   # or
   docker compose up -d notification-dispatcher-v2
   ```

2. **Monitor logs** for delivery success/failure rates
   ```bash
   docker compose logs -f notification-dispatcher-v2
   ```

3. **Compare metrics** between Go and Python dispatchers
   - Check Prometheus/Grafana for delivery latency, success rate
   - Verify no duplicate deliveries (both should claim different rows)

4. **When confident, stop Go dispatcher**
   ```bash
   docker compose stop notification-dispatcher
   ```

5. **Remove Go service from docker-compose** (Phase 6)

### Instant Rollback

Stop Python dispatcher:
```bash
make ndisp2-rollback
# or
docker compose stop notification-dispatcher-v2
```

Go dispatcher continues handling all retries.

---

## Validation

### Build
```bash
make ndisp2-build
```
✅ Docker image builds successfully

### Health Check
```bash
curl http://localhost:8091/health
# {"service":"notification-dispatcher-v2","status":"ok"}

curl http://localhost:8091/ready
# {"ready":true}
```
✅ Endpoints respond

### Database Polling
```bash
docker compose logs -f notification-dispatcher-v2
```
✅ Polls database without errors, claims and delivers stuck rows

---

## Files Changed

```
services/notification-dispatcher-v2/
├── src/
│   ├── __init__.py
│   ├── main.py          (FastAPI app + lifecycle)
│   ├── config.py        (Pydantic settings)
│   ├── dispatcher.py    (Polling loop + claim/deliver logic)
│   └── channels.py      (Slack, Webhook, Browser, Email channels)
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── PHASE5_MIGRATION.md  (this file)

docker-compose.yml       (added notification-dispatcher-v2 service)
Makefile                 (added ndisp2-* targets)
MIGRATION.md             (Phase 5 complete)
```

**Total:** 11 files, 878 lines added

---

## Next Steps (Phase 6)

Delete polyglot artifacts:
- Remove `services/notification-dispatcher/` (Go)
- Remove `services/streaming-hub/` (Go, already replaced by streaming-hub-v2)
- Remove `services/temporal-workers/go-worker/` (Go, already replaced by Python workers)
- Remove `services/temporal-workers/go-workflows/` (Go, already ported to Python)
- Remove `services/gateway/` (Rust, already replaced by gateway-v2)
- Remove `Cargo.*`, `go.mod`, `proto/`, `gen/go/`, etc.

See `MIGRATION.md` Phase 6 for details.
