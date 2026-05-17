# Observability: Prometheus & Grafana

## Purpose

Every FastAPI service and worker exposes `/metrics`; Prometheus scrapes
them on a 15s interval. Grafana renders the provisioned dashboards.

## Source

- `observability/prometheus.yml`
- `observability/alert-rules.yml`
- `observability/grafana/provisioning/`
- `observability/grafana/dashboards/`
- `src/observability/metrics.py` — helpers (Counter, Histogram, Gauge)
- `src/observability/budget_metrics.py` — background refresh task

## Metric catalogue (highlights)

| Metric | Type | Labels |
|---|---|---|
| `autoniix_http_requests_total` | Counter | service, method, path, status |
| `autoniix_http_request_duration_seconds` | Histogram | service, path |
| `autoniix_workflow_phase_duration_seconds` | Histogram | workflow, phase |
| `autoniix_workflow_phase_failures_total` | Counter | workflow, phase |
| `autoniix_db_pool_active` / `_max` / `_pressure` | Gauge | service |
| `autoniix_temporal_queue_depth` | Gauge | task_queue |
| `autoniix_provider_call_total` | Counter | category, provider, outcome |
| `autoniix_provider_call_cost_usd` | Counter | category, provider |
| `autoniix_budget_remaining_usd` | Gauge | scope (test/prod) |
| `autoniix_video_status` | Gauge | channel_id, status |
| `autoniix_intelligence_savings_usd_total` | Counter | service |

## Dashboards

- **Pipeline Overview** — workflow throughput, phase durations, success rate
- **Budget** — cumulative + remaining; per-channel ranking
- **Diversity Floor** — % of videos blocked by similarity dedup
- **Prediction Calibration** — Brier / weighted fraction per niche / model
- **Fleet** — DB pool pressure, Temporal queue, service latency

All provisioned automatically on first boot via
`observability/grafana/provisioning/`.

## Retention

Prometheus TSDB: 15 days (`--storage.tsdb.retention.time=15d`).

## Hosted access

With the `tls` profile, Grafana lives at `https://${GRAFANA_DOMAIN}` with
its own login (Traefik’s admin-auth middleware is skipped to avoid
double-prompt).

## Related pages

- [[Observability-Logs-Loki]] · [[Observability-Alerts]] ·
  [[Cost-Analysis]] · [[Architecture-Network-And-Gateway]]
