# Load test harness

These tests hit a *running* stack and enforce throughput / latency SLOs.
Skipped by default — they need the dashboard BFF reachable at
`DASHBOARD_BASE_URL` (default `http://localhost:8000`) and an admin token
in `DASHBOARD_TOKEN`.

## Why pure-pytest, not k6 / locust

- Same language as the rest of the codebase — no second toolchain to
  install in CI.
- Async-native: a single test process can drive 100s of concurrent
  requests with `asyncio.gather` + `httpx.AsyncClient`.
- SLOs are encoded as Python assertions — failures show up in the same
  pytest report as unit tests.

When this gets noisy (e.g. needs sustained-rate load, ramp-up curves, or
multi-region origin tests), graduate to k6. That's a Phase 7 concern.

## Run

```bash
# 1. Bring up the stack (docker compose up)
# 2. Get an admin token (POST /api/auth/login)
# 3. Run the load suite:
DASHBOARD_BASE_URL=http://localhost:8000 \
DASHBOARD_TOKEN=$TOKEN \
pytest tests/load -v
```
