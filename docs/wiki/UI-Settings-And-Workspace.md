# UI: Settings & Workspace

## Routes

| Route | File |
|---|---|
| `/dashboard/settings` | `settings/page.tsx` |
| `/dashboard/settings/[section]` | dynamic |
| `/dashboard/workspace` | `workspace/page.tsx` |

## Settings

Three main blocks:

1. **System config** — editable list of `system_config` rows backed by
   `systemApi.config()` / `systemApi.updateConfig()`. Includes the
   environment-mode toggle (TEST ↔ PRODUCTION) with a confirmation dialog
   that lists the financial implications.
2. **Emergency stop** — single red button. When active, banners across
   the app inform every user; a second click resumes.
3. **Clean-slate** — owner-only, test-mode-only. Drops every test
   artefact (MinIO `test/` prefix + tagged DB rows).

## Workspace

- Workspace name + rename (owner)
- Members table with role chip; owner can change roles, remove members
- Pending invites with copy-link / revoke / resend buttons
- Invite form: email + role dropdown
- Workspace switcher in `AppHeader` (only visible when user has > 1)

## Related pages

- [[BFF-System-And-FleetHealth]] · [[BFF-Workspaces-And-Multitenancy]] ·
  [[Test-vs-Production-Mode]]
