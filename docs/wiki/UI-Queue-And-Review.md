# UI: Queue & Review

## Routes

| Route | File |
|---|---|
| `/dashboard/queue` | `queue/page.tsx` |
| `/dashboard/review` | `review/page.tsx` |

## Queue

Shows pending jobs awaiting scheduling slots, plus the next 24h of
upcoming Temporal Schedule fires (from `GET /api/v2/system/schedule`).

Useful for sanity-checking that `DailySchedulerWorkflow` will pick up the
right channels tomorrow.

## Review

Human-in-the-loop queue. Each item is a video whose composite score fell
within 0.5 of the threshold; the workflow paused at `awaiting_review`.

For each item:
- Thumbnail + title + description
- Quality breakdown (per-dimension scores with traffic-light colours)
- Operator notes field
- Buttons: **Approve**, **Reject**, **Request changes**

Approved → the workflow resumes and proceeds to delivery. Rejected →
failed status, no further work. Request changes → workflow restarts from
the script phase with the notes injected into the prompt.

## Related pages

- [[BFF-Notifications-Review-Users-Flags]] · [[Quality-Gates]] ·
  [[Workflow-VideoProduction]]
