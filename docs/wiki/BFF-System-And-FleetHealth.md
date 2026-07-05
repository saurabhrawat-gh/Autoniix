# BFF: System & Fleet Health

## Purpose

System-wide controls: `system_config` CRUD, emergency stop / resume, fleet
health (DB pool pressure + Temporal queue depth), environment mode toggle,
and the clean-slate utility for test environments.

## Source

- `src/services/dashboard/v2/system.py:1-150`
- BFF main: `src/services/dashboard/main.py` `/api/fleet-health`

## Endpoints (`/api/v2/system/...`)

| Method + Path | Role | Purpose |
|---|---|---|
| `GET  /system/config` | admin+ | All keys |
| `PUT  /system/config` | admin+ | Patch one key |
| `POST /system/emergency-stop` | admin+ | Sets `system_config.emergency_stop=TRUE`; every running workflow short-circuits on its next `check_system_status` |
| `POST /system/emergency-resume` | admin+ | Clears emergency-stop |
| `GET  /system/fleet-health` | member+ | Aggregated metrics (see below) |
| `GET  /system/environment` | member+ | Test vs production mode |
| `POST /system/clean-slate` | owner | Test-mode only: deletes all `test/` MinIO objects + truncates test-tagged DB rows |

## Fleet health payload

```json
{
  "db_pool": {
    "active": 4,
    "max":   10,
    "pressure": 0.40            // active / max
  },
  "temporal_queue_depth": 0,
  "workers": {
    "production":  {"healthy": true,  "task_queue": "video-production"},
    "scheduler":   {"healthy": true,  "task_queue": "scheduler"}
  },
  "services": [
    {"name": "research",  "healthy": true,  "latency_ms": 8},
    ...
  ],
  "env": "test",
  "emergency_stop": false
}
```

Fleet health drives the trigger for `postgres-read-replicas`
(`docs/future/PENDING.md`) — sustained `db_pool.pressure > 0.5` for > 1h.

## Environment toggle

Flipping mode calls `set_db_mode_override(mode)` in
`src/environment.py` which updates the 5-second cache and the
`system_config.environment_mode` row, so providers re-resolve on the next
request **without service restart**.

## Clean-slate

The destructive `POST /system/clean-slate`:

1. Requires `is_test()` (raises 409 otherwise).
2. Calls `storage_provider.delete_prefix("test/")`.
3. `DELETE FROM job_events WHERE environment='test'` etc.
4. Resets the test daily counters.

## Related pages

- [[Test-vs-Production-Mode]] · [[Observability-Prometheus-Grafana]] ·
  [[UI-Settings-And-Workspace]]
