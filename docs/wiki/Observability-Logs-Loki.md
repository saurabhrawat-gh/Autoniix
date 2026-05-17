# Observability: Logs (Loki + Promtail)

## Purpose

Centralised log aggregation. Promtail tails every Docker container’s
stdout, ships structured logs to Loki, and Grafana renders them next to
metrics.

## Source

- `observability/loki-config.yml`
- `observability/promtail-config.yml`
- All services use `structlog` (JSON output) so labels include service,
  level, event, and correlation id.

## Retention

30 days (configured in `loki-config.yml`). Disk-bounded; old streams are
garbage-collected automatically.

## Standard structured fields

```json
{
  "timestamp": "2026-05-17T11:00:00Z",
  "level": "info",
  "event": "provider.instantiated",
  "service": "voice",
  "category": "tts",
  "name": "fishaudio",
  "content_id": "VID_sleep-recovery_20260517_103022",
  "channel_id": "sleep-recovery"
}
```

Workflow logs additionally include `workflow_id`, `run_id`, and `phase`.

## Common LogQL queries

```
{service="worker-production"} |~ "phase_failed"
{service="voice"}             | json | provider="elevenlabs"
{service=~".+", level="error"} | json
```

## Correlation

The `content_id` is propagated as a structlog context var from the
workflow root, so every log line in every service for one video can be
pulled in a single LogQL query.

## Related pages

- [[Observability-Prometheus-Grafana]] · [[Observability-Alerts]]
