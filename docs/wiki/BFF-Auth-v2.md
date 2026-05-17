# BFF: Auth v2

## Purpose

JWT-based multi-user auth, MFA, password reset, rate-limiting, with a
backwards-compatible legacy single-password mode controlled by feature
flags.

## Source

- `src/services/dashboard/v2/auth.py:1-700`
- `src/services/dashboard/v2/_deps.py` — `Principal` + `get_principal`
- `src/services/dashboard/_limiter.py` — slowapi backing store

## Feature flags

| Key | Effect |
|---|---|
| `auth.legacy.enabled` | When true, `/login` accepts the legacy single password and the dashboard offers the legacy login form |
| `auth.v2.enabled` | When true, dashboard offers email + password (+ MFA) login |
| `auth.multi_tenant.enabled` | When true, workspace switching and invitations are exposed |

Both `legacy` and `v2` can be true during migration; only `v2` once the
2-week stability window in production passes.

## Public endpoints

| Method + Path | Notes |
|---|---|
| `GET  /api/v2/auth/mode` | Returns `{legacy: bool, v2: bool, mfa_required: bool}` |
| `POST /api/v2/auth/register` | Email + password; creates a personal workspace, makes the user its owner |
| `POST /api/v2/auth/login` | Email + password (+ TOTP if MFA) → access + refresh JWT |
| `POST /api/v2/auth/refresh` | Rotate access token; re-embeds `wid` claim |
| `POST /api/v2/auth/forgot-password` | Email reset link (1h token) |
| `POST /api/v2/auth/reset-password` | Token + new password |
| `GET  /api/v2/auth/invite-info?token=` | Used by `/accept-invite` page |
| `POST /api/v2/auth/accept-invite` | Creates account if needed + joins workspace |

## Authenticated endpoints

| Method + Path | Purpose |
|---|---|
| `GET  /api/v2/auth/me` | Current principal |
| `GET  /api/v2/auth/workspaces` | All workspaces this user belongs to |
| `POST /api/v2/auth/switch-workspace` | Sets `active_workspace_id`, returns new tokens with the updated `wid` claim |
| `POST /api/v2/auth/mfa/setup` | TOTP enroll |
| `POST /api/v2/auth/mfa/verify` | Enable after one good code |
| `POST /api/v2/auth/mfa/disable` | Requires current TOTP |

## JWT claims

```json
{
  "sub":  "<user_id>",
  "wid":  <active_workspace_id>,
  "role": "owner|admin|member",
  "exp":  <unix>,
  "iat":  <unix>,
  "jti":  "<random>"
}
```

Legacy sessions — created before v2 — default to `wid=1` (the bootstrap
workspace) via the migration in
`scripts/migrations/202605160001_multitenant_activate.sql`.

## Rate limiting

Login endpoints are wrapped with slowapi at **10 req / minute / IP**.
A distributed limiter would back this with Redis; current implementation
is per-process and adequate for single-instance BFF.

## Related pages

- [[BFF-Workspaces-And-Multitenancy]] · [[Security-Authn-Authz]] ·
  [[UI-Auth-Pages]]
