# Test vs Production System

## Overview

The system supports two environment modes:

| Feature | Test Mode (default) | Production Mode |
|---|---|---|
| **LLM** | `mock_llm` (cached + GPT-4o-mini fallback) | OpenAI GPT-4o / Anthropic / Google |
| **TTS** | `edge_tts` (free Microsoft Edge TTS) | Fish Audio / ElevenLabs |
| **Images** | `placeholder` (Pillow-generated) | DALL-E |
| **Search** | `mock_search` (cache + Wikipedia) | SerpAPI |
| **Storage** | MinIO under `test/` prefix | MinIO under `prod/` prefix |
| **YouTube** | Skipped entirely | Full upload (private by default) |
| **Render** | 640×360, 15fps, preview quality | Full HD, 30fps, high quality |
| **Content IDs** | `TEST_VID_...` | `VID_...` |
| **Cost/video** | ~$0.00 | ~$0.12–$0.35 |
| **Daily budget** | $5.00 (configurable) | $50.00 (configurable) |
| **Max videos/day** | 10 (configurable) | Unlimited |

## Architecture

```
┌─────────────────────────────────────────────────┐
│  src/environment.py                              │
│  ├─ get_mode() → "test" | "production"          │
│  ├─ is_test() / is_production()                  │
│  ├─ require_production(action)                   │
│  ├─ get_storage_prefix() → "test" | "prod"       │
│  └─ get_content_id_prefix() → "TEST_VID" | "VID" │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  src/providers/registry.py                       │
│  ├─ _TEST_PROVIDER_MAP (auto-remap in test)     │
│  └─ ProviderRegistry.get() checks is_test()     │
└─────────────────────────────────────────────────┘
```

### Mode Resolution Order
1. **DB override** — `system_config.environment_mode` (set by dashboard toggle)
2. **Env var** — `ENVIRONMENT_MODE` / `Settings.environment_mode`
3. **Default** — `"test"`

## Configuration

### Environment Variable
```env
ENVIRONMENT_MODE=test
```

### Database Keys (`system_config`)
| Key | Default | Description |
|---|---|---|
| `environment_mode` | `test` | Current mode |
| `environment_switched_at` | `` | ISO timestamp of last switch |
| `environment_switched_by` | `` | Who switched |
| `test_daily_budget_limit` | `5.00` | Max USD/day in test |
| `test_max_videos_per_day` | `10` | Max videos/day in test |
| `test_cost_alert_threshold` | `2.00` | Alert threshold in test |

## API Endpoints

### GET /api/environment
Returns current mode, switch history, and production cost estimates.

### PUT /api/environment
Switch mode. Body:
```json
{"mode": "production", "confirm": true}
```
- Switching to production **requires** `confirm: true`
- Switching to test does not require confirmation

### GET /api/test-data/stats
Returns test video count, total cost, job event count.

### DELETE /api/test-data
Cleans up all test data from DB and MinIO `test/` prefix.

## Safety Guards

1. **Delivery service** — `is_test()` check blocks YouTube upload at the service level
2. **Workflow pipeline** — `is_test_mode` flag skips delivery activity entirely
3. **Daily scheduler** — Reads `environment_mode` from DB, passes to all child workflows
4. **Budget enforcement** — Test mode uses `test_daily_budget_limit` ($5) instead of production limit ($50)
5. **Video count cap** — Test mode limits to `test_max_videos_per_day` (10)
6. **Production confirmation** — Dashboard requires explicit `confirm: true` to switch to production
7. **Storage isolation** — All files prefixed with `test/` or `prod/` — never mixed
8. **DB tagging** — `videos`, `feedback_loop`, `job_events` all have `environment` column

## Dashboard UI

- **Header pill** — Green "TEST" or red pulsing "PRODUCTION" indicator
- **Banners** — Context-aware banners below header
- **Confirmation dialog** — Red warning dialog when switching to production with cost estimates
- **Stats** — `/api/stats` response includes `environment_mode`

## Running Tests

```bash
pytest tests/test_environment_mode.py -v
```

## Switching Modes

### Via Dashboard
Click the environment pill in the header. Production requires confirmation dialog.

### Via API
```bash
# Switch to production
curl -X PUT http://localhost:8020/api/environment \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode": "production", "confirm": true}'

# Switch back to test
curl -X PUT http://localhost:8020/api/environment \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode": "test"}'
```

### Via Environment Variable
```bash
ENVIRONMENT_MODE=production docker compose up -d
```
