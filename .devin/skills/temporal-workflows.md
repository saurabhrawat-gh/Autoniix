# Skill: Temporal Workflows

**Use when:** Working with Temporal workflow definitions, activities, signals, queries, workers, or retry policies in this codebase.

**When NOT to use:** General Python async programming unrelated to Temporal orchestration.

---

## Workflow Definitions

| Workflow                 | File                     | Task Queue       | Schedule          |
| ------------------------ | ------------------------ | ---------------- | ----------------- |
| DailySchedulerWorkflow   | daily_scheduler.py       | scheduler        | Every 6 hours     |
| VideoProductionWorkflow  | video_production.py      | video-production | On-demand (child) |
| ModelMaintenanceWorkflow | model_maintenance.py     | scheduler        | Weekly cron       |
| AnalyticsWorkflow        | (in video_production.py) | analytics        | Weekly            |
| TrendScanWorkflow        | (in video_production.py) | analytics        | Every 8 hours     |

## Key Patterns

### Activity Execution

```python
result = await workflow.execute_activity(
    activity_function,
    args,
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(maximum_attempts=3, ...),
)
```

### Retry Policies

- `RETRY_STANDARD`: 3 attempts, 10s initial, 2x backoff, 60s max. Non-retryable: BudgetExceededError, ValidationError.
- `RETRY_RENDER`: 2 attempts, 30s initial, 5min max.

### Signals (VideoProductionWorkflow)

- `approve_video(approved: bool)` — human review gate
- `emergency_stop()` — cancel immediately
- `pause_workflow()` / `resume_workflow()` — pause/resume

### Queries

- `get_status()` → {phase, accrued_cost, human_approved, paused, cancelled}

### Worker Registration

Workers are in `src/workers/`. Each worker registers activities and starts polling a task queue. New activities must be registered in the corresponding worker file.

### Job Events

`emit_job_event(content_id, phase, status, ...)` is called between every phase. Stored in `job_events` table. Used by dashboard WebSocket for real-time progress.
