# Schedules

## Purpose

Five Temporal **Schedules** are registered idempotently after first deploy.
The Schedule object owns a cron spec and a workflow start action; Temporal
guarantees one execution per cron tick even across worker restarts.

## Source

- `scripts/register_schedules.py:1-138`
- `Makefile` target: `make schedule-register`

## Schedules

| Schedule ID | Workflow | Cron (UTC) |
|---|---|---|
| `gate-calibration-weekly` | `GateCalibrationWorkflow` | `0 4 * * 0` Sun 04:00 |
| `niche-pulse-weekly` | `NichePulseRefreshWorkflow` | `0 5 * * 0` Sun 05:00 |
| `retention-fetch-daily` | `RetentionFetchWorkflow` | `0 3 * * *` daily 03:00 |
| `model-maintenance-weekly` | `ModelMaintenanceWorkflow` | `0 6 * * 0` Sun 06:00 |
| `daily-scheduler` | `DailySchedulerWorkflow` | `0 7 * * *` daily 07:00 |

Ordering on Sundays is deliberate: gate-calibration first (uses outcomes),
then niche-pulse (fresh trends), then model-maintenance (retrains using
the up-to-date data).

## Registration

```bash
make schedule-register             # via Makefile
python -m scripts.register_schedules --temporal-host temporal:7233
```

The script is **idempotent**: existing schedules with the same ID are left
alone (RPC `already exists` → skip). Re-running after editing cron is
not supported — delete in Temporal UI first, then re-register.

## Inspection

In the Temporal Web UI (`https://temporal.<domain>`), Schedules tab shows
last-run + next-run timestamps and lets you trigger ad-hoc runs.

## Related pages

- [[Workers-And-Activities]]
- [[Workflow-DailyScheduler]]
- [[Workflow-GateCalibration]] · [[Workflow-NichePulseRefresh]] ·
  [[Workflow-RetentionFetch]] · [[Workflow-ModelMaintenance]]
