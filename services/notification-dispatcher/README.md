# notification-dispatcher (G1)

Go microservice that retries stuck notification deliveries.

## What it does

Polls `notification_deliveries` for rows that are:
- `status='queued'` older than `STALE_AFTER_MS` (default 60s), **or**
- `status='failed'` with `attempts < MAX_ATTEMPTS` older than the same window

For each claimed row it calls the appropriate channel (slack, webhook,
browser, email) and updates the row to `sent` or `failed`.

Uses `FOR UPDATE SKIP LOCKED` so multiple dispatcher replicas coexist safely.

## What it does NOT do

- **Does not** replace Python's `src/services/dashboard/v2/_notify.py`.
  Python still creates the notification row, creates delivery rows, and
  attempts primary delivery synchronously. This service only picks up
  rows Python left in `queued`/`failed` state past the stale window.
- **Does not** own the notification event bus. That is (still) Python +
  the Rust gateway's `notifications.rs`.

Cutting Python out of the primary path is a follow-up migration tracked
separately — this service is additive by design so it can be deployed
without behavior change.

## Env vars

| Var | Default | Purpose |
| --- | ------- | ------- |
| `DATABASE_URL` | — | Postgres connection string (required) |
| `NDISP_HTTP_ADDR` | `:8090` | Where `/health` + `/ready` listen |
| `NDISP_POLL_INTERVAL_MS` | `15000` | How often to poll |
| `NDISP_STALE_AFTER_MS` | `60000` | Age at which a row is considered stuck |
| `NDISP_BATCH_SIZE` | `50` | Rows per tick |
| `NDISP_MAX_ATTEMPTS` | `3` | Total delivery attempts before permanent failure |
| `SLACK_WEBHOOK_URL` | — | Fallback used if a route has no `webhook_url` in its config |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warn`/`error` |

## Build

```bash
# From repo root
docker build -f go/Dockerfile --build-arg BINARY_PATH=./notification-dispatcher/cmd/dispatcher -t notification-dispatcher ./go
```

Or via docker-compose (opt-in profile, see below).

## Run in docker-compose

The service is defined under the `go-services` profile so `docker-compose up`
does **not** start it by default. Enable it explicitly:

```bash
docker-compose --profile go-services up notification-dispatcher
```

## Tests

```bash
cd go
go test ./notification-dispatcher/...
```

Channel tests use `httptest.NewServer` — no live network needed.
Dispatcher tests use mock channels + a real pool is only exercised in
harness integration tests (deferred; see `docs/architecture/harness-engineering-plan.md`).
