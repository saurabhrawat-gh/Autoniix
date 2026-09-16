# Notification Dispatcher v2 (Python)

**Status:** Phase 5 migration — replaces Go G1 service  
**Language:** Python 3.11+ (FastAPI + asyncpg)  
**Responsibility:** Poll `notification_deliveries` for stuck rows and retry delivery

---

## Overview

This service is a **direct port** of the Go notification-dispatcher (`services/notification-dispatcher/`). It polls the `notification_deliveries` table for rows that are:

- `status='queued'` AND older than `STALE_AFTER_MS`, OR
- `status='failed'` AND `attempts < MAX_ATTEMPTS` AND older than `STALE_AFTER_MS`

It claims rows using `FOR UPDATE SKIP LOCKED` to avoid collisions with other dispatcher instances or Python's inline delivery, then retries delivery via the configured channel (slack, webhook, browser, email).

---

## Architecture

### Channels

| Channel   | Description                                 | Config                                   |
| --------- | ------------------------------------------- | ---------------------------------------- |
| `slack`   | Posts to Slack Incoming Webhook             | `webhook_url` or `SLACK_WEBHOOK_URL` env |
| `webhook` | POSTs raw notification JSON to URL          | `url` in route config                    |
| `browser` | No-op (served by notification center UI)    | N/A                                      |
| `email`   | Placeholder (always fails until SMTP wired) | N/A                                      |

### Polling Loop

1. Every `POLL_INTERVAL_MS` (default 15s), claim up to `BATCH_SIZE` (default 50) stale rows
2. For each row, invoke the channel's `send()` method with `HTTP_TIMEOUT_MS` (default 10s)
3. On success: mark `status='sent'`, record response
4. On failure: mark `status='failed'`, record error
5. Rows with `attempts >= MAX_ATTEMPTS` are left in `status='failed'` permanently

---

## Configuration

All env vars are optional with sensible defaults:

| Env Var             | Default                                           | Description                                      |
| ------------------- | ------------------------------------------------- | ------------------------------------------------ |
| `DATABASE_URL`      | `postgresql://app:...@postgres-app:5432/autoniix` | App database connection string                   |
| `HTTP_ADDR`         | `0.0.0.0:8090`                                    | Health/ready endpoint listen address             |
| `POLL_INTERVAL_MS`  | `15000`                                           | How often to poll for work (ms)                  |
| `STALE_AFTER_MS`    | `60000`                                           | Min age before claiming a row (ms)               |
| `BATCH_SIZE`        | `50`                                              | Max rows claimed per tick                        |
| `MAX_ATTEMPTS`      | `3`                                               | Total delivery attempts before permanent failure |
| `HTTP_TIMEOUT_MS`   | `10000`                                           | Timeout for each channel HTTP call (ms)          |
| `SLACK_WEBHOOK_URL` | `""`                                              | Fallback Slack webhook if route config has none  |

---

## Endpoints

- `GET /health` — Liveness probe (always returns 200)
- `GET /ready` — Readiness probe (checks DB connectivity)

---

## Local Development

```bash
cd services/notification-dispatcher-v2

# Install deps
pip install -e .

# Copy env template
cp .env.example .env

# Edit DATABASE_URL to point to local postgres-app
# (default: postgresql://app:change_me_strong_random_64@localhost:5433/autoniix)

# Run
python -m src.main
```

Service listens on `http://localhost:8090` by default.

---

## Docker

```bash
docker build -t notification-dispatcher-v2 .
docker run -p 8090:8090 --env-file .env notification-dispatcher-v2
```

---

## Testing

```bash
pip install -e ".[dev]"
pytest
```

---

## Cutover from Go

### Current State

- **Go dispatcher:** `services/notification-dispatcher/` (G1 service)
- **Python dispatcher:** `services/notification-dispatcher-v2/` (this service)

### Rollout

1. Deploy Python dispatcher alongside Go dispatcher
2. Both poll the same table; `FOR UPDATE SKIP LOCKED` prevents collisions
3. Monitor logs for delivery success/failure rates
4. When confident, stop Go dispatcher
5. Remove Go service from docker-compose (Phase 6)

### Rollback

Stop Python dispatcher:

```bash
docker-compose stop notification-dispatcher-v2
```

Go dispatcher continues handling all retries.

---

## Differences from Go

### Parallel Delivery

**Go:** Sequential (one row at a time in the loop)  
**Python:** Parallel (`asyncio.gather` over all rows in batch)

### HTTP Client

**Go:** `http.Client` with per-request timeout  
**Python:** `httpx.AsyncClient` with global timeout + connection pooling

### Logging

**Go:** `zap.SugaredLogger`  
**Python:** `structlog` with JSON output

---

## Files

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
└── README.md
```

---

## Next Steps

- Wire into `docker-compose.yml` with Traefik labels (if needed) or standalone
- Add Makefile targets: `ndisp2-build`, `ndisp2-test`, `ndisp2-up`, `ndisp2-rollback`
- Integration test: insert stuck row, verify dispatcher picks it up and marks sent
- Update `MIGRATION.md` Phase 5 complete
