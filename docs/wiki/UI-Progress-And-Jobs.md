# UI: Progress & Jobs

## Routes

| Route | File |
|---|---|
| `/dashboard/progress` | `progress/page.tsx` |
| `/dashboard/jobs/[id]` | `jobs/[id]/page.tsx` |

## Progress page

Live view of all active jobs (queued/running/paused) plus recently
stopped/failed/completed in side rails.

For each active job a card shows:

- Channel name + content mode + content_id
- Per-phase progress dots from `WORKFLOW_PHASES`
- Accrued cost
- Buttons: **Pause** · **Resume** · **Stop** · **Settings**

Live updates via `wsProgress(content_id)` (WebSocket to
`/api/ws/progress/{id}`). Reconnect with exponential backoff up to 30s.

### Stopped vs failed

The two states are visually distinct:

- **Stopped** (orange border / background) — user-initiated. Buttons:
  **Resume** (restart from checkpoint) **+** **Retry** (fresh).
- **Failed** (red border) — error path. Only **Retry**.
- **Superseded** (muted) — “Superseded” label, no actions.

## Job detail page

Three tabs:

1. **Progress** — timeline view from `GET /jobs/{id}/progress`. If the job
   is stopped/failed, surfaces an orange/red panel with the resume/retry
   buttons.
2. **Output** — thumbnail preview, video player, YouTube link if uploaded.
3. **Metadata** — title, description, tags, SEO scores; editable for
   awaiting-review items, read-only otherwise.

If the job is awaiting human review (composite score borderline), an
**Approve** / **Reject** / **Request changes** action bar is shown.

## Related pages

- [[BFF-Jobs-And-Content]] · [[Workflow-VideoProduction]] ·
  [[UI-Queue-And-Review]]
