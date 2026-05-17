# UI: Dashboard Home & Channels

## Routes

| Route | File |
|---|---|
| `/dashboard` | `dashboard/src/app/dashboard/page.tsx` |
| `/dashboard/channels` | `channels/page.tsx` |
| `/dashboard/channels/new` | `channels/new/page.tsx` |
| `/dashboard/channels/[id]` | `channels/[id]/page.tsx` |
| `/dashboard/channels/[id]/settings` | `channels/[id]/settings/page.tsx` |

## Home (`/dashboard`)

Shows the daily/weekly stats cards, an environment-mode banner (red
pulsing PRODUCTION or green TEST pill in `AppHeader`), and a list of all
channels with quick triggers and status pills.

Stats are fetched via `dashboardApi.stats()` which proxies
`GET /api/v2/system/fleet-health` plus `GET /api/v2/content/stats`.

Three-dot action menu per channel:

- **Duplicate** — `POST /channels/{id}/clone`
- **Export** — `GET /channels/{id}/export` triggers JSON download
- **Archive** — confirmation dialog → `PUT /channels/{id}/archive`

Archived channels live in a collapsible “Archived Channels” section at the
bottom of the list and re-enter the main list via Restore (which sets
`status=disabled` — the operator must explicitly re-enable).

## Channels list (`/dashboard/channels`)

Filterable + sortable table. `include_archived` query param controls
visibility. The Create button routes to `/dashboard/channels/new`.

## Channel detail (`/dashboard/channels/[id]`)

Two tabs: **Long-form** and **Shorts**, each with:

- Trigger button (disabled if a job is already running)
- Pause / Resume / Stop controls
- Recent jobs list (links into `/dashboard/jobs/[id]`)
- Channel info side-panel
- If archived: banner across the top with Restore button

## New channel (`/dashboard/channels/new`)

Form fields with inline hints/tooltips: name, niche, brand, language,
voice_id, schedule (long_per_week, short_per_week, upload_times_utc),
auto_upload, banned topics.

## Related pages

- [[BFF-Channels]] · [[UI-Progress-And-Jobs]] · [[Service-Brand]]
