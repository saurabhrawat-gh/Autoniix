# UI: Auth Pages

Public pages outside the authenticated shell.

## Routes

| Route | File | Purpose |
|---|---|---|
| `/login` | `dashboard/src/app/login/page.tsx` | Dual-mode: legacy single-password OR v2 email/password (+ MFA step) |
| `/register` | `dashboard/src/app/register/page.tsx` | New user signup; creates personal workspace |
| `/forgot-password` | `dashboard/src/app/forgot-password/page.tsx` | Request password-reset link |
| `/accept-invite` | `dashboard/src/app/accept-invite/page.tsx` | Public page used by invite emails; creates account if needed and joins the workspace |
| `/` | `dashboard/src/app/page.tsx` | Redirect: `/login` if no token, else `/dashboard` |

## Login flow

1. On mount, `GET /api/v2/auth/mode` decides which form to render.
2. Legacy: single password field → `POST /api/auth/login` (legacy).
3. v2: email + password → `POST /api/v2/auth/login`. If response is
   "MFA required" the UI swaps to a 6-digit TOTP step.
4. On success, store `access_token` + `refresh_token` in `localStorage`
   via `setToken()` from `api-v2.ts`, then redirect to `/dashboard`.

## Accept-invite flow

1. URL: `/accept-invite?token=<...>`.
2. `GET /api/v2/auth/invite-info?token=` returns
   `{email, role, workspace_name, user_exists}`.
3. If `user_exists=false`, show a name + password form and call
   `POST /api/v2/auth/accept-invite { token, password, name }`.
4. If `user_exists=true`, just call `accept-invite` with current session
   (or require login first). Server creates the membership row and issues
   new tokens with the new workspace as `wid`.

## Related pages

- [[BFF-Auth-v2]] · [[BFF-Workspaces-And-Multitenancy]]
