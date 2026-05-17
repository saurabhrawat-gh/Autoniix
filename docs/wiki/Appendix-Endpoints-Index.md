# Appendix: Endpoints Index

Flat list of every BFF endpoint and the v1 → v2 equivalence. Auth and
role requirements noted where they differ from the default of
`member+ in workspace`.

## Auth v2

| Method | Path | Role |
|---|---|---|
| GET  | `/api/v2/auth/mode` | public |
| POST | `/api/v2/auth/register` | public |
| POST | `/api/v2/auth/login` | public, rate-limited |
| POST | `/api/v2/auth/refresh` | public |
| POST | `/api/v2/auth/forgot-password` | public, rate-limited |
| POST | `/api/v2/auth/reset-password` | public, rate-limited |
| GET  | `/api/v2/auth/invite-info` | public |
| POST | `/api/v2/auth/accept-invite` | public |
| GET  | `/api/v2/auth/me` | member+ |
| GET  | `/api/v2/auth/workspaces` | member+ |
| POST | `/api/v2/auth/switch-workspace` | member+ |
| POST | `/api/v2/auth/mfa/setup` | member+ |
| POST | `/api/v2/auth/mfa/verify` | member+ |
| POST | `/api/v2/auth/mfa/disable` | member+ |

## Workspace

| Method | Path | Role |
|---|---|---|
| GET  | `/api/v2/workspace` | member+ |
| PUT  | `/api/v2/workspace` | owner |
| GET  | `/api/v2/workspace/members` | admin+ |
| DELETE | `/api/v2/workspace/members/{id}` | owner |
| PUT  | `/api/v2/workspace/members/{id}/role` | owner |
| GET  | `/api/v2/workspace/invites` | admin+ |
| POST | `/api/v2/workspace/invites` | admin+ |
| DELETE | `/api/v2/workspace/invites/{id}` | admin+ |

## Channels

See [[BFF-Channels]] — 12 endpoints under `/api/v2/channels`.

## Jobs + Content

See [[BFF-Jobs-And-Content]] — ~14 endpoints under `/api/v2/jobs` and
`/api/v2/content`, plus the two WebSockets.

## System

See [[BFF-System-And-FleetHealth]] — 7 endpoints.

## Providers + Experiments

See [[BFF-Providers-And-Experiments]] — ~10 endpoints.

## Library / Notifications / Review / Users / Flags

See individual BFF pages.

## Service-direct (not via BFF)

Each FastAPI service also exposes its own `/health`, `/metrics`, and
task-specific endpoints. Internal callers (Temporal activities) hit
these directly on the docker network.

## Deprecated

42 `/api/*` paths flagged `deprecated=True`. See
[[BFF-Legacy-API-Deprecation]].

## Related pages

- [[BFF-Auth-v2]] (every other BFF-* page)
- [[Appendix-Env-Vars]] · [[Appendix-Glossary]]
