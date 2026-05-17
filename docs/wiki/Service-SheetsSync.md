# Service: Sheets Sync

## Purpose

Optional Google Sheets bridge. Lets non-technical operators view channel
inventory, configure schedules, and seed ideation lists in a familiar UI.
Reads/writes the spreadsheet via the Google Sheets API.

## Port / source

- Port `8011`, memory 256M
- `src/services/sheets_sync/main.py`

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /sync-channels` | Pull channel tab → `channels` table |
| `POST /sync-ideation` | Pull ideation tab → research seeds |
| `POST /push-stats` | Push daily stats back to Sheets |

## Config

- `GOOGLE_SHEETS_ID` — the spreadsheet (default in `src/config.py:110`)
- `GOOGLE_SHEETS_CREDENTIALS_JSON` — service-account JSON

## Related pages

- `scripts/setup-sheets.gs` (Apps Script) · [[BFF-Channels]]
