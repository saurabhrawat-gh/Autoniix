# Observability: Alerts

## Purpose

Proactive paging. Prometheus evaluates 12 alert rules; Alertmanager
routes firing alerts to Slack (and email/Telegram via the BFF for some
classes).

## Source

- `observability/alert-rules.yml` (12 rules)
- `observability/alertmanager.yml` (Slack webhook routing)
- `SLACK_WEBHOOK_URL` env var on Alertmanager

## Rule overview (selected)

| Alert | Condition | Severity |
|---|---|---|
| `HighErrorRate` | 5xx rate > 5% over 5m | warning |
| `HighLatencyP95` | p95 > 5s over 5m | warning |
| `WorkflowFailureSpike` | failures/h > 3 | critical |
| `DBPoolSaturated` | `db_pool_pressure > 0.85` for 10m | warning |
| `TemporalQueueBackingUp` | queue depth > 20 for 10m | warning |
| `BudgetExhausted` | `budget_remaining_usd < 0` | critical |
| `EmergencyStopActive` | `system_config.emergency_stop=TRUE` for 30m | warning |
| `ProviderDown` | health_check false for 10m | warning |
| `RetentionFetchStale` | no rows in 36h | warning |
| `ModelDrift` | Brier > 0.30 OR PSI > 0.35 | warning |
| `MinioUnreachable` | scrape fail 5m | critical |
| `DiskAlmostFull` | filesystem < 10% | critical |

## Calibration

Defaults are intentionally cautious. The `alert-rules-calibration` watch
window in `PENDING.md` (Week 1 after deploy) is the cue to tune these
against observed baselines.

## Routing

All alerts route to one Slack channel by default. The Alertmanager config
supports per-severity routes — expand when on-call rotation is added.

## Inhibitions

`MinioUnreachable` inhibits dependent alerts (storage-touching workflows
failing) for the duration of the outage to avoid noise.

## Related pages

- [[Operations-Runbook]] · [[Observability-Prometheus-Grafana]]
