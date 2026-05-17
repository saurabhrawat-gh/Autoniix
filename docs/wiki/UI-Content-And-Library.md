# UI: Content & Library

## Routes

| Route | File |
|---|---|
| `/dashboard/content` | `content/page.tsx` |
| `/dashboard/content/[id]` | `content/[id]/page.tsx` (or similar) |
| `/dashboard/library` | `library/page.tsx` |

## Content page

Historical video table with filters: channel, status, content mode,
date range. Status pills: queued, running, paused, stopped (orange),
superseded (muted), failed (red), completed (green). Clicking a row
opens the job detail page.

Uses `contentApi.list`, `contentApi.detail`, `jobsApi.output`,
`jobsApi.metadata` from `dashboard/src/lib/api-v2.ts`.

## Library (DAM)

Grid of local assets (videos + images). Each tile shows a preview,
duration, tags. Click → detail drawer with description, presigned URL,
edit-tags form, delete button.

Upload button drops a file + auto-generates SBERT embedding server-side.
Search input runs a semantic query via `damApi.search`.

## Related pages

- [[BFF-Library-DAM]] · [[Service-Assets]]
