# BFF: Workspaces & Multi-tenancy

## Purpose

Every resource (channel, video, system_config row, etc.) is scoped to a
workspace. Users belong to one or more workspaces and have a role per
workspace. All v2 endpoints filter on the JWT’s `wid` claim.

## Source

- `src/services/dashboard/v2/workspace.py:1-700`
- `src/services/dashboard/v2/_deps.py` (Principal.workspace_id default `1`)
- `scripts/migrations/202605160001_multitenant_activate.sql`

## Data model

```sql
workspaces (id, name, created_at, owner_user_id)
workspace_members (workspace_id, user_id, role, joined_at)
workspace_invitations (id, workspace_id, email, role, token, sent_at, accepted_at, resent_at)
users.active_workspace_id  -- last switched-to workspace
```

## Roles

| Role | Capabilities |
|---|---|
| owner | Manage members, invite, archive workspace, all admin tasks |
| admin | Manage channels, providers, system_config |
| member | View + run jobs, no destructive ops |

## Endpoints (workspace + invitations)

| Method + Path | Auth | Purpose |
|---|---|---|
| `GET  /api/v2/workspace` | member+ | Current workspace details |
| `PUT  /api/v2/workspace` | owner | Rename / settings |
| `GET  /api/v2/workspace/members` | admin+ | List members |
| `DELETE /api/v2/workspace/members/{user_id}` | owner | Remove member |
| `PUT  /api/v2/workspace/members/{user_id}/role` | owner | Change role |
| `GET  /api/v2/workspace/invites` | admin+ | List pending invites |
| `POST /api/v2/workspace/invites` | admin+ | Create invite (email, role) |
| `DELETE /api/v2/workspace/invites/{id}` | admin+ | Revoke |

## Switching workspaces

`POST /api/v2/auth/switch-workspace { workspace_id }` updates
`users.active_workspace_id` and re-issues access/refresh tokens with the
new `wid` claim. The dashboard reloads on success so all in-flight queries
pick up the new scope.

## Scoping enforcement

Every v2 query is parameterised on `p.workspace_id` (the Principal’s `wid`).
Legacy v1 endpoints were marked `deprecated=True`; until they are removed,
they effectively run as workspace 1.

## Related pages

- [[BFF-Auth-v2]] · [[UI-Settings-And-Workspace]] · [[Security-Authn-Authz]]
