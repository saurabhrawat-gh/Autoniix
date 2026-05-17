# BFF: Jobs & Content

## Purpose

The job lifecycle surface: list active jobs, watch progress, fetch output
+ metadata, approve/reject the human-review gate, and (re)start / stop /
pause / resume running workflows.

## Source

- `src/services/dashboard/v2/jobs.py:1-300` — job actions
- `src/services/dashboard/v2/content.py:1-500` — content/video listing
- `src/services/dashboard/main.py` WS handlers `/api/ws/progress/{id}` + `/api/ws/events`

## Job statuses (`src/schemas/common.py`)

```python
class VideoStatus(str, Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    stopped = "stopped"        # user-initiated stop, resumable
    superseded = "superseded"  # replaced by a retry; hidden from active views
    failed = "failed"          # error path; retry only
    completed = "completed"
```

## Endpoints (`/api/v2/jobs/...`)

| Method + Path | Purpose |
|---|---|
| `GET  /jobs/active` | Active list (running/paused/queued) — proxies legacy Temporal-aware view |
| `GET  /jobs/{id}/progress` | Live Temporal status + per-phase timeline (also reads `videos.checkpoint`, `error_message`) |
| `GET  /jobs/{id}/output` | URLs to thumbnail, rendered video, YouTube link |
| `GET  /jobs/{id}/metadata` | Title, description, tags, SEO scores |
| `POST /jobs/{id}/approve` | Sends `approve_video(True)` signal |
| `POST /jobs/{id}/reject` | Sends `approve_video(False)` |
| `POST /jobs/{id}/retry` | Marks old job `superseded`, starts a fresh workflow |
| `POST /jobs/{id}/restart` | Resumes from checkpoint (works for `failed` and `stopped`) |
| `POST /jobs/{id}/pause` | `pause_workflow` signal |
| `POST /jobs/{id}/resume` | `resume_workflow` signal |
| `POST /jobs/{id}/stop`   | `emergency_stop` signal, marks status=stopped |

Every write endpoint records an `audit_log` row with the actor + action.

## Endpoints (`/api/v2/content/...`)

| Method + Path | Purpose |
|---|---|
| `GET  /content?status=&channel_id=&page=` | Paginated history |
| `GET  /content/{id}` | Single video record |
| `GET  /content/stats` | Per-status counts for dashboard cards |
| `POST /content/trigger` | Convenience wrapper around channel trigger |

## Resume vs retry

- **Retry** — fresh `content_id`, ignores checkpoint, re-runs every phase.
  Old job is marked `superseded` so it stops counting toward limits.
- **Restart / Resume** — same `content_id`, reads `videos.checkpoint`,
  hydrates phase outputs via `load_checkpoint_data`, resumes from the
  failed/stopped phase.

## WebSocket

`GET /api/ws/progress/{content_id}` — polls `job_events` every 2s and
streams `{phase, state, detail, cost}` to the client. UI shows live phase
ticks on the Progress page.

## Related pages

- [[Workflow-VideoProduction]] · [[UI-Progress-And-Jobs]] ·
  [[Appendix-Glossary]]
