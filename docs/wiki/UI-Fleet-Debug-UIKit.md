# UI: Fleet, Debug, UI Kit

## Routes

| Route | File |
|---|---|
| `/dashboard/fleet` | `fleet/page.tsx` |
| `/dashboard/debug` | `debug/page.tsx` |
| `/dashboard/ui-kit` | `ui-kit/page.tsx` |

## Fleet

Real-time view of the stack:

- DB pool active/max + pressure %
- Temporal queue depth
- Worker health (`worker-production`, `worker-scheduler`)
- Per-service health + p50/p95 latency
- Model health table (per-niche GBM staleness + Brier)

Watch for: sustained `db_pool.pressure > 0.5` (→ surface
`postgres-read-replicas` from docs/future/PENDING.md), Temporal queue depth backing
up (→ `worker-auto-scaling`).

Data source: `systemApi.fleetHealth()` polled every 5 seconds.

## Debug

Developer-only utility page. Surfaces:

- Raw fleet-health JSON
- Last 100 audit log entries
- Active experiments
- Provider registry state per category
- Manual workflow trigger form (skip dashboard validations)

## UI Kit

Living style guide — every shared component (Button, Card, Tooltip,
StatusPill, PhaseDot, Tip, Modal, etc.) rendered in light + dark theme.
Useful when adding new pages.

## Related pages

- [[BFF-System-And-FleetHealth]] · [[UI-Theming-And-Components]]
