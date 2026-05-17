# Workers & Activities

## Purpose

Temporal workers register workflows + activities and pull work from a task
queue. Two workers run in this stack.

## Source

- `src/workers/run_production.py:1-102`
- `src/workers/run_scheduler.py:1-101`
- `src/workers/activities/*.py`

## worker-production (task queue `video-production`)

Registers `VideoProductionWorkflow` and 23 activities.

Pipeline activities (in order):

| Activity | Module |
|---|---|
| `research_activity` | `activities/research.py` |
| `script_activity`, `title_activity` | `activities/script.py` |
| `voice_activity` | `activities/voice.py` |
| `assets_activity` | `activities/assets.py` |
| `thumbnail_activity` | `activities/thumbnail.py` |
| `direction_activity` | `activities/direction.py` |
| `music_activity` | `activities/music.py` |
| `assembly_activity` | `activities/assembly.py` |
| `render_activity` | `activities/render.py` |
| `delivery_activity`, `compute_metadata_activity` | `activities/delivery.py` |
| `analytics_activity` | `activities/analytics.py` |
| `brand_activity` | `activities/brand.py` |
| `editor_activity` | `activities/editor.py` |

Infrastructure activities:

| Activity | Purpose |
|---|---|
| `update_video_status(content_id, phase, channel_id, title, content_mode)` | UPDATE `videos.status` + `videos.checkpoint` |
| `emit_job_event(content_id, channel_id, phase, state, detail, cost?)` | INSERT into `job_events` |
| `acquire_channel_lock(channel_id)` / `release_channel_lock(channel_id)` | Redis SETNX 6h TTL |
| `check_system_status()` | Emergency-stop + budget + daily-video-count |
| `get_eligible_channels(content_mode)` | Channels due today, excluding running/stopped/superseded |
| `send_notification(event, message, level?)` | Telegram + Slack |
| `save_checkpoint_data(content_id, phase, data)` / `load_checkpoint_data(content_id, phase)` | Resume-from-checkpoint |

Concurrency knobs (`src/config.py:76-83`):

- `temporal_production_max_activities` (default 5)
- `temporal_production_max_workflow_tasks` (default 10)
- `temporal_default_activity_start_to_close_s` (1800 = 30 min)
- `temporal_default_activity_heartbeat_s` (60s)

## worker-scheduler (task queue `scheduler`)

Registers 5 scheduled workflows and their activities:

| Workflow | Cron | Notes |
|---|---|---|
| `DailySchedulerWorkflow` | `0 7 * * *` | Trigger production for eligible channels |
| `GateCalibrationWorkflow` | `0 4 * * 0` | Weekly threshold tuning |
| `NichePulseRefreshWorkflow` | `0 5 * * 0` | Weekly trend signal refresh |
| `RetentionFetchWorkflow` | `0 3 * * *` | Daily retention-curve ingestion |
| `ModelMaintenanceWorkflow` | `0 6 * * 0` | Weekly ML retrain |

Concurrency: `temporal_scheduler_max_activities` (default 3).

Activities shared with production worker: `check_system_status`,
`get_eligible_channels`, `acquire_channel_lock`, `send_notification`.

## Activity wrapping convention

Most activity modules are tiny adapters that call a FastAPI service over
HTTP. Example pattern (`activities/research.py`):

```python
@activity.defn(name="research_activity")
async def research_activity(params: dict) -> dict:
    async with httpx.AsyncClient(timeout=600) as c:
        r = await c.post(f"http://research:8001/research", json=params)
        r.raise_for_status()
        return r.json()
```

Real activity modules also emit per-attempt heartbeats and propagate the
current `environment` mode into request payloads.

## Related pages

- [[Workflow-VideoProduction]]
- [[Schedules]]
- [[Service-Research]] (and every other [[Service-*]] page)
