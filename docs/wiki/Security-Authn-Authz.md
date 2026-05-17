# Security: AuthN & AuthZ

## Purpose

Protect the dashboard, the BFF, and any sensitive endpoint with strong
authentication and role-based authorization.

## AuthN summary

- **Legacy mode** — single shared password from
  `system_config.dashboard_admin_password`. Backwards-compat only; flag
  `auth.legacy.enabled` toggles availability.
- **v2 mode** — JWT (HS256), email + password (bcrypt), optional TOTP MFA
  enrolled by the user.
- **Dual mode** — both can be on during migration so existing operators
  keep working while users onboard onto v2.

Flag flip:

```bash
make auth-enable     # sets auth.v2.enabled=TRUE, leaves legacy on
# After 2 stable weeks in production with zero errors on legacy paths,
# disable legacy + remove the /api/* endpoints (see legacy-api-removal).
```

## JWT mechanics

- **Access token** — 15 min TTL, embeds `sub`, `wid`, `role`, `jti`.
- **Refresh token** — 7 day TTL, separate secret, opaque to clients.
- **Secret guard** — `_jwt_secret()` raises `RuntimeError` at startup if
  `AUTH_JWT_SECRET` equals a known default (`change_me`, `CHANGE_ME`,
  blank, etc.) in production mode.
- **Rotation** — switch `AUTH_JWT_SECRET` and restart BFF; legacy tokens
  fail closed and users re-login.

## MFA

TOTP (RFC 6238), 30s window, secret stored in `users.mfa_secret`
(encrypted at rest with `MFA_SECRET_KEY`, deferred until the multi-user
trigger fires). Backup codes not yet implemented.

## RBAC

Three roles per workspace: `owner`, `admin`, `member`. Enforced at
endpoint declaration in `_deps.py` via `require_role("admin")` style
dependencies that 403 if `Principal.role` doesn’t meet the bar.

## Audit log

Every write-endpoint inserts an `audit_log` row with `actor`,
`workspace_id`, `action`, `target`, `detail`. Read-able by owners on
`/dashboard/debug`.

## Rate limiting

slowapi at 10 req/min/IP on login + reset endpoints. The middleware
bypasses for the in-app self-test calls (origin == BFF’s own URL).

## Related pages

- [[BFF-Auth-v2]] · [[BFF-Workspaces-And-Multitenancy]] ·
  [[Providers-Secrets]]
