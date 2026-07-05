# BFF: Legacy /api/* Deprecation

## Purpose

Forty-two pre-v2 endpoints under `/api/*` still ship in
`src/services/dashboard/main.py` for backwards compatibility. They are
flagged `deprecated=True` in OpenAPI and will be removed when the trigger
below fires.

## Trigger to remove

`auth.v2.enabled=TRUE` in production for **≥ 2 weeks** AND zero errors
recorded for the deprecated paths in Grafana/Loki.

From `docs/future/PENDING.md` (section `legacy-api-removal`):

> Remove endpoints in two passes:
> 1. Read endpoints first (`GET /api/channels`, `GET /api/jobs/*`, etc.)
> 2. Write endpoints second (`POST /api/channels/{id}/trigger`, etc.)
> Legacy `dashboard/src/lib/api.ts` can be deleted at the same time.

## Untouched legacy paths

These stay (utility, not data):

- `POST /api/auth/login` (legacy single-password) when
  `auth.legacy.enabled=TRUE`.
- `GET /api/health`, `/api/fleet-health`.
- WebSockets `/api/ws/progress/{content_id}` and `/api/ws/events`.

## Equivalence table (excerpt)

| Legacy | v2 replacement |
|---|---|
| `GET  /api/channels` | `GET  /api/v2/channels` |
| `POST /api/channels` | `POST /api/v2/channels` |
| `POST /api/channels/{id}/trigger` | `POST /api/v2/channels/{id}/trigger` |
| `GET  /api/jobs/{id}/progress` | `GET  /api/v2/jobs/{id}/progress` |
| `POST /api/jobs/{id}/approve` | `POST /api/v2/jobs/{id}/approve` |
| `GET  /api/config` | `GET  /api/v2/system/config` |
| `POST /api/emergency-stop` | `POST /api/v2/system/emergency-stop` |

(Full mapping in `dashboard/src/lib/api-v2.ts` next to the deprecation
note on `dashboard/src/lib/api.ts`.)

## Related pages

- [[BFF-Auth-v2]] · [[BFF-Jobs-And-Content]] · [[Appendix-Endpoints-Index]]
