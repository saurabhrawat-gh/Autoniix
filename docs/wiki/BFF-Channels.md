# BFF: Channels

## Purpose

CRUD plus lifecycle (enable/disable/archive/restore/clone/export) for
YouTube channels. The single biggest module in the BFF (~45KB).

## Source

- `src/services/dashboard/v2/channels.py:1-1100`

## Endpoints

| Method + Path | Role | Purpose |
|---|---|---|
| `GET    /api/v2/channels?include_archived=false` | member+ | List |
| `POST   /api/v2/channels` | admin+ | Create |
| `GET    /api/v2/channels/{id}` | member+ | Detail |
| `PUT    /api/v2/channels/{id}` | admin+ | Update config |
| `DELETE /api/v2/channels/{id}` | owner | Hard delete (reserved) |
| `PUT    /api/v2/channels/{id}/enable` | admin+ | status=active |
| `PUT    /api/v2/channels/{id}/disable` | admin+ | status=disabled |
| `PUT    /api/v2/channels/{id}/archive` | admin+ | status=archived, pauses running |
| `PUT    /api/v2/channels/{id}/restore` | admin+ | status=disabled (must re-enable) |
| `POST   /api/v2/channels/{id}/clone` | admin+ | Duplicates config under new id |
| `GET    /api/v2/channels/{id}/export` | admin+ | Full config JSON |
| `POST   /api/v2/channels/{id}/trigger?content_mode=long\|short` | member+ | Start a `VideoProductionWorkflow` |
| `POST   /api/v2/channels/{id}/pause` | member+ | Pause all running workflows for channel |
| `POST   /api/v2/channels/{id}/resume` | member+ | Resume |
| `POST   /api/v2/channels/{id}/stop`   | admin+ | Stop active jobs (status=stopped) |
| `GET    /api/v2/channels/{id}/jobs` | member+ | Recent jobs for channel |

## Channel record

```json
{
  "id": "sleep-recovery",
  "workspace_id": 7,
  "name": "Sleep & Recovery",
  "niche": "sleep",
  "brand_id": "body-signals",
  "status": "active|disabled|archived",
  "auto_upload": true,
  "schedule_config": {
    "long_per_week": 1,
    "short_per_week": 7,
    "upload_times_utc": ["14:00"]
  },
  "language": "en",
  "voice_id": "...",
  "created_at": "..."
}
```

## Triggering

`trigger` validates: workspace match, channel `status=active`, no
existing `running`/`paused` job, daily budget remaining. Creates a `videos`
row, starts a Temporal workflow with `VideoParams`, returns `content_id`
that the UI can subscribe to via WebSocket.

## Related pages

- [[Workflow-VideoProduction]] · [[BFF-Jobs-And-Content]] ·
  [[UI-Dashboard-Home-And-Channels]]
