# BFF: Notifications, Review, Users, Flags

## Purpose

Four smaller modules under the v2 router.

## Notifications — `v2/notifications.py`

| Method + Path | Purpose |
|---|---|
| `GET  /api/v2/notifications` | List (paginated, `unread_only`) |
| `POST /api/v2/notifications/{id}/read` | Mark read |
| `POST /api/v2/notifications/read-all` | Mark all read |
| `GET  /api/v2/notifications/preferences` | Channel-level prefs |
| `PUT  /api/v2/notifications/preferences` | Update prefs |

Notifications come from three sources:
- Workflow `send_notification` activity (Telegram + Slack + in-app)
- Alertmanager webhooks
- System events (workspace invite, quota warning, etc.)

## Review — `v2/review.py`

Human-in-the-loop review queue. When a workflow’s composite score is
borderline (within 0.5 of threshold) it stops at `awaiting_review` and the
UI shows it on `/dashboard/review`.

| Method + Path | Purpose |
|---|---|
| `GET  /api/v2/review/queue` | Items awaiting decision |
| `POST /api/v2/review/{id}/approve` | Signal workflow approve |
| `POST /api/v2/review/{id}/reject` | Signal workflow reject |
| `POST /api/v2/review/{id}/request-changes` | Re-runs from script phase with operator notes |

## Users — `v2/users.py`

| Method + Path | Role | Purpose |
|---|---|---|
| `GET  /api/v2/users/me` | member+ | Self profile |
| `PUT  /api/v2/users/me` | member+ | Update display name, avatar |
| `POST /api/v2/users/me/change-password` | member+ | Old + new |

## Flags — `v2/flags.py`

Reads selected `system_config` rows that act as feature flags so the
frontend can render conditionally without an admin round-trip.

| Method + Path | Purpose |
|---|---|
| `GET  /api/v2/flags` | Public feature-flag snapshot |

## Related pages

- [[BFF-Auth-v2]] · [[UI-Notifications-Users-Profile]] · [[UI-Queue-And-Review]]
