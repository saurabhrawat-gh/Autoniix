# Workflow: DailySchedulerWorkflow

## Purpose

Runs daily at **07:00 UTC** and starts a `VideoProductionWorkflow` for
every eligible channel.

## Source

- `src/temporal_workflows/daily_scheduler.py`
- Schedule: `scripts/register_schedules.py` id `daily-scheduler`

## Logic

1. `check_system_status` — returns `paused`, `daily_budget_remaining_usd`,
   `videos_today`. Bails if emergency-stop active or budget exhausted.
2. `get_eligible_channels(content_mode)` — yields channels whose schedule
   matches today (long-form 1×/week, short 7×/week per channel by default),
   excluding any channel that already has a running, stopped, or paused
   job (`stopped`/`superseded`/`running` filter).
3. For each eligible channel:
   - `acquire_channel_lock(channel_id)` (Redis SETNX with 6h TTL).
   - Start child `VideoProductionWorkflow` (parent close policy:
     `ABANDON` — child outlives parent so worker restarts don’t cascade).
4. `send_notification("daily_scheduler_done", "…")` — Telegram + Slack.

## Task queue

`scheduler` — served by `worker-scheduler`.

## Limits

- `temporal_scheduler_max_activities` (default 3) — caps parallel channel
  iteration to keep DB / Temporal frontend from being overwhelmed when
  fleet > 50 channels.
- Per-channel daily budget caps applied by `check_system_status`:
  - Test mode: `test_daily_budget_limit` (default $5), `test_max_videos_per_day` (10).
  - Production: `daily_budget_limit_usd`, `max_videos_per_day`.

## Related pages

- [[Workflow-VideoProduction]]
- [[Schedules]]
- [[Workers-And-Activities]]
