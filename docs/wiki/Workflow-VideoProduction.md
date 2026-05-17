# Workflow: VideoProductionWorkflow

## Purpose

The end-to-end durable pipeline that produces one video. Lives in
`src/temporal_workflows/video_production.py:1-960`. Triggered ad-hoc from
the dashboard or on schedule by `DailySchedulerWorkflow`.

## Source

- `src/temporal_workflows/video_production.py`
- `src/workers/run_production.py` — registration
- `src/schemas/common.py` — `VideoParams`, `VideoResult`, `VideoStatus`

## Task queue

`video-production` — served by the `worker-production` container.

## Inputs

```python
class VideoParams(BaseModel):
    channel_id: str
    content_mode: str          # "long" | "short"
    max_cost_usd: float
    environment: str = "test"  # "test" | "production"
    content_id: str | None = None   # used on resume / restart
    resume_from_phase: str | None = None
    # optional fields: niche, topic_override, schedule_publish_at, ...
```

## Phases

```python
# src/temporal_workflows/video_production.py:27-38
WORKFLOW_PHASES = [
    "researching",
    "brand_check",
    "scripting",
    "generating_voice",
    "generating_assets",
    "directing",
    "post_production",
    "rendering",
    "delivering",
    "analytics",
]
```

(Additional sub-phases for thumbnail and editor run between these.)

## Retry policies

```python
RETRY_STANDARD = RetryPolicy(
    maximum_attempts=3,
    initial_interval=10s,
    backoff_coefficient=2.0,
    maximum_interval=60s,
    non_retryable_error_types=["BudgetExceededError", "ValidationError"],
)

RETRY_RENDER = RetryPolicy(
    maximum_attempts=2,
    initial_interval=30s,
    maximum_interval=5m,
)
```

## Signals

| Signal | Effect |
|---|---|
| `approve_video(approved: bool)` | Human review gate — approve or reject |
| `emergency_stop()` | Hard stop — sets `_cancelled=True`, fails workflow |
| `pause_workflow()` | Sets `_paused=True`; next `_check_pause` blocks |
| `resume_workflow()` | Clears pause; resumes from current phase |

Paused workflows auto-cancel after **24h** (`_check_pause` uses
`workflow.wait_condition` with a 24h timeout).

## Queries

```python
@workflow.query
def get_status() -> dict:
    return {
      "phase": self._current_phase,
      "accrued_cost": self._accrued_cost,
      "human_approved": self._human_approved,
      "paused": self._paused,
      "cancelled": self._cancelled,
    }
```

Used by `dashboard-bff` `GET /jobs/{id}/progress`.

## Phase-level instrumentation

Every phase calls these helpers:

```python
async def _set_phase(content_id, phase, channel_id): ...
async def _complete_phase(content_id, channel_id, phase, cost=0, detail=None): ...
async def _fail_phase(content_id, channel_id, phase, error=""): ...
async def _check_pause(): ...   # blocks if paused; raises if cancelled
async def _save_phase_data(content_id, phase, data): ...   # checkpoint write
async def _load_phase_data(content_id, phase) -> dict: ...  # checkpoint read
```

Under the hood `_set_phase`/`_complete_phase`/`_fail_phase` execute the
`emit_job_event` activity which writes to the `job_events` table. The
dashboard’s `/api/ws/progress/{content_id}` WebSocket polls that table every
2 seconds.

## Resume from checkpoint

If `params.resume_from_phase` is set, `_should_skip(phase, resume_from)`
short-circuits all earlier phases. `_load_phase_data` re-hydrates outputs
persisted by `save_checkpoint_data` so downstream phases see the same inputs
as the original run. Used by the dashboard’s **Resume** button on stopped jobs.

## Budget guard

```python
def _check_budget(budget: dict):
    if budget["accrued_cost_usd"] > budget["max_cost_usd"]:
        raise RuntimeError("Budget exceeded")
```

Called after every cost-incurring activity. In test mode all providers are
mock so accrued_cost is ~0.

## Quality gates

After each phase, the workflow records a per-dimension score (e.g.
`script_structure_score`, `hook_retention_score`). At the end a **composite
score** is computed and compared against `THRESHOLDS`. Below threshold →
rewrite (up to 3 for script) / regeneration (up to 2 for thumbnail) /
human-review escalation. See [[Quality-Gates]].

In test mode all thresholds are forced to 0 (`is_test_mode` branch at
`video_production.py:193-200`) so the pipeline never blocks for QA failures.

## Activities called (in order)

1. `update_video_status`, `emit_job_event` — every phase
2. `research_activity`
3. `brand_activity`
4. `script_activity`, `title_activity`
5. `voice_activity`
6. `assets_activity`
7. `thumbnail_activity`
8. `direction_activity`
9. `music_activity`
10. `editor_activity`
11. `assembly_activity`
12. `render_activity` (uses `RETRY_RENDER`)
13. `compute_metadata_activity`, `delivery_activity`
14. `analytics_activity`

Plus infrastructure: `save_checkpoint_data`, `load_checkpoint_data`,
`check_system_status`, `acquire_channel_lock`, `release_channel_lock`,
`send_notification`.

## Related pages

- [[Workers-And-Activities]]
- [[Quality-Gates]]
- [[BFF-Jobs-And-Content]]
- [[UI-Progress-And-Jobs]]
