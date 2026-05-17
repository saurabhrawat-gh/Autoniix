# UI: Theming & Components

## Source

- `dashboard/src/app/globals.css`
- `dashboard/src/lib/utils.ts` — phase labels, status colour helpers
- `dashboard/src/lib/api-v2.ts` — unified API client + WebSocket helpers
- `dashboard/.eslintrc.json`, `dashboard/scripts/check-ui-tokens.mjs`

## Design tokens

Defined as CSS variables in `globals.css`. Includes a brand palette,
semantic colour roles (`success`, `warning`, `error`, `tertiary`), and
shades for both light and dark themes. The `check-ui-tokens.mjs` script
fails the build if a Tailwind class with a hard-coded colour sneaks in.

## Status colour map (`utils.ts`)

```ts
const statusColor = {
  queued:     "text-blue-600 bg-blue-50",
  running:    "text-emerald-600 bg-emerald-50",
  paused:     "text-amber-600 bg-amber-50",
  stopped:    "text-orange-600 bg-orange-50",
  failed:     "text-rose-600 bg-rose-50",
  superseded: "text-zinc-500 bg-zinc-100",
  completed:  "text-green-700 bg-green-50",
  archived:   "text-zinc-500 bg-zinc-100",
  active:     "text-emerald-700 bg-emerald-50",
  disabled:   "text-zinc-500 bg-zinc-100",
};
```

Helpers: `isTerminalStatus`, `isStopped`, `isSuperseded`, `statusIcon`,
`statusDot`, `PHASE_LABELS`.

## Lockdown frost

`.lockdown-frost` is a global CSS overlay applied when emergency-stop is
active: blur 1px + dim overlay 25% (light) / 35% (dark). Click events on
running-job buttons are still permitted (admins can resume); destructive
controls are disabled.

## Tooltip system

CSS-only `.has-tooltip` + `.tooltip-text` pattern. Used throughout for
button/field hints to avoid pulling in a runtime tooltip library.

## API client (`api-v2.ts`)

Thin wrapper around `fetch` with automatic token refresh on 401, base URL
resolution from `NEXT_PUBLIC_API_URL` (or relative path proxied via
Next.js rewrites in dev), and `wsProgress()` / `wsEvents()` helpers for
the two WebSocket streams.

## Related pages

- [[UI-Fleet-Debug-UIKit]] · [[BFF-Auth-v2]]
