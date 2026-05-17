# Service: Admin

## Purpose

Lightweight CRUD endpoints kept separate from the dashboard BFF for
operational scripts and one-off admin tasks (channel bulk import,
`system_config` patch, etc.). Not normally exposed to the public.

## Port / source

- Port `8009`, memory 256M
- `src/services/admin/main.py`

## Endpoints

| Method + Path | Purpose |
|---|---|
| `GET/POST/PUT/DELETE /channels` | Channel CRUD |
| `GET/PUT /system-config` | Patch any `system_config` key |
| `POST /prompt-registry` | Add/update a prompt version |
| `POST /backfill` | Trigger one-shot backfill jobs |

Protected by `ADMIN_JWT_SECRET` and not routed through Traefik in the
default setup (port 8009 only on the docker network).

## Related pages

- [[BFF-Channels]] · [[DB-Seed-Data]] · [[Operations-Runbook]]
