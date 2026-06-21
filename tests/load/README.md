# Load test harness

Two complementary load tests live here.

## 1. `test_fleet_health_under_load.py` — pytest, SLO smoke

Pure-pytest load smoke that hits a *running* stack and enforces basic
throughput / latency SLOs via async `httpx`. Skipped by default — needs
the dashboard BFF reachable at `DASHBOARD_BASE_URL` (default
`http://localhost:8000`) and an admin token in `DASHBOARD_TOKEN`.

### Why pure-pytest, not k6 / locust

- Same language as the rest of the codebase — no second toolchain to
  install in CI.
- Async-native: a single test process can drive 100s of concurrent
  requests with `asyncio.gather` + `httpx.AsyncClient`.
- SLOs are encoded as Python assertions — failures show up in the same
  pytest report as unit tests.

### Run

```bash
# 1. Bring up the stack (docker compose up)
# 2. Get an admin token (POST /api/v2/auth/login)
# 3. Run the load suite:
DASHBOARD_BASE_URL=http://localhost:8000 \
DASHBOARD_TOKEN=$TOKEN \
pytest tests/load -v
```

## 2. `auth_load_test.js` — k6, sustained load against Rust gateway

Per HARNESS-ENGINEERING-PLAN.md §14. Three load profiles, all targeting
the Rust gateway:

| Mode | Endpoint | Target p95 | Target error |
|------|----------|------------|--------------|
| (default) | `POST /api/v2/auth/register` | <200ms | <0.1% |
| `TEST_MODE=signin` | `POST /api/v2/auth/signin` (after seed) | <100ms | <0.1% |
| `TEST_MODE=me` | `GET /api/v2/me` (after seed + signin) | <50ms | <0.01% |

### Run

```bash
# Default ramp: register storm
k6 run tests/load/auth_load_test.js

# Read-heavy /me workload (mirrors production traffic shape)
k6 run --env TEST_MODE=me tests/load/auth_load_test.js

# Compare Rust vs Python on the same workload
k6 run --env TEST_BOTH=true tests/load/auth_load_test.js

# Override base URLs
RUST_GATEWAY_URL=https://gateway.dev.autoniix.com \
  k6 run tests/load/auth_load_test.js
```

Requires [k6](https://k6.io) installed locally (`brew install k6` on macOS).

When the pytest smoke gets noisy (e.g. needs sustained-rate load, ramp-up
curves, or multi-region origin tests), the k6 suite is the authoritative
load harness; the pytest one stays as a fast SLO smoke for PR CI.
