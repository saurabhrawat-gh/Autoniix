# UI: Notifications, Users, Profile

## Routes

| Route | File |
|---|---|
| `/dashboard/notifications` | `notifications/page.tsx` |
| `/dashboard/users` | `users/page.tsx` |
| `/dashboard/profile` | `profile/page.tsx` |

## Notifications

Paginated inbox; toggle `Unread only`. Each item links to its source
(job page, workspace settings, etc.) when applicable. Per-channel
preferences (in-app / email / Telegram / Slack) for each event type:

- Job completed / failed
- Awaiting human review
- Budget warning (80% threshold)
- Quota warning (YouTube)
- Workspace invite accepted
- System alert

## Users

Owner-only. Lists every user with their roles per workspace. Used in
multi-workspace deployments (consultancies running several brand
portfolios under one Autoniix install).

## Profile

Self-service: display name, avatar, password change, MFA enroll/disable.
No workspace controls here (see [[UI-Settings-And-Workspace]]).

## Related pages

- [[BFF-Notifications-Review-Users-Flags]] · [[BFF-Auth-v2]]
