# Golden Fixtures

Per `HARNESS-ENGINEERING-PLAN.md §A4`.

Each `.json` file captures a Python v2 response that the Rust gateway must match.

## Directory layout

```
tests/golden/
  auth/          ← /api/v2/auth/* endpoints
  channels/      ← /api/v2/channels/* endpoints
  users/         ← /api/v2/users/* endpoints
  workspace/     ← /api/v2/workspace/* endpoints
  notifications/ ← /api/v2/notifications/* endpoints
  flags/         ← /api/v2/flags/* endpoints
  system/        ← /api/v2/system/* endpoints
  voice/         ← /api/v2/voice/* endpoints
  providers/     ← /api/v2/providers/* (B1 — credentials, chains, categories)
  library/       ← /api/v2/library/* (B3 — assets, DAM assets, collections, tags)
  content/       ← /api/v2/content/* (B6 — list, trigger history)
  finishing/     ← /api/v2/finishing/* (B6 — presets)
  review/        ← /api/v2/review/* (B5 — queue)
```

## Fixture schema

```json
{
  "method": "GET",
  "path": "/api/v2/auth/mode",
  "request_body": null,
  "status": 200,
  "body": { "mode": "email" },
  "ignore_fields": ["created_at", "updated_at", "id", "user_id", "workspace_id"]
}
```

| Field | Description |
|---|---|
| `method` | HTTP method (GET/POST/PUT/DELETE) |
| `path` | Absolute path including `/api/v2/` |
| `request_body` | JSON body to send (null for GET) |
| `status` | Expected HTTP status code |
| `body` | Expected response body (subset match) |
| `ignore_fields` | Fields skipped during comparison (dynamic values like timestamps, IDs) |

## Capturing new fixtures

Run the capture script against a live Python dashboard:

```bash
PYTHON_DASHBOARD_URL=http://localhost:8000 \
RUST_GATEWAY_URL=http://localhost:8080 \
python scripts/capture-golden.py --output tests/golden
```

## Replaying in CI

```bash
RUST_GATEWAY_URL=http://localhost:8080 \
TEST_DATABASE_URL=postgresql://... \
cargo test -p harness --test golden_replay_test -- --test-threads=1
```
