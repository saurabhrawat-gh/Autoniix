# Autoniix Dashboard UI Kit

Internal component library for the Autoniix dashboard. All primitives live in
`dashboard/src/lib/ui/`, are themed via CSS variables (see `tokens.md`), and
re-export from a single barrel `@/lib/ui`.

## Quickstart

```tsx
import { Button, Card, Input, Dialog } from '@/lib/ui';
```

Browse the full gallery at **`/dashboard/ui-kit`** — every primitive in every
variant. Toggle the theme from the header to verify dark/light parity.

## Inventory

| Primitive                | Built on                       | Replaces                                |
| ------------------------ | ------------------------------ | --------------------------------------- |
| `Button`                 | Radix Slot + CVA               | `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-tonal` classes |
| `Input`, `Textarea`, `Label` | native + Radix Label       | raw `<input>` / `<textarea>`            |
| `Select`                 | `@radix-ui/react-select`       | native `<select>`                       |
| `Checkbox`, `RadioGroup`, `Switch` | Radix                | native checkbox/radio chrome            |
| `Card` family            | div + CVA                      | `.card` / `.card-elevated` classes      |
| `Badge`                  | span + CVA                     | `.badge` / `.chip-short` / `.chip-long` |
| `Skeleton`               | div + `animate-shimmer`        | ad-hoc loading placeholders             |
| `Dialog`                 | `@radix-ui/react-dialog`       | `fixed inset-0` modal patterns          |
| `DropdownMenu`           | `@radix-ui/react-dropdown-menu`| ad-hoc 3-dot menus                      |
| `Popover`                | `@radix-ui/react-popover`      | one-off positioned panels               |
| `Tabs`                   | `@radix-ui/react-tabs`         | ad-hoc tab strips                       |
| `Tooltip`, `SimpleTooltip` | `@radix-ui/react-tooltip`    | `.has-tooltip` CSS pattern              |
| `Separator`              | Radix                          | `<hr>` / divider divs                   |
| `Kbd`                    | native `<kbd>`                 | inline keycap markup                    |

## Theming rules

1. Use only token classes (`bg-surface-*`, `text-content-*`, `border-border`,
   `text-status-*`, `bg-accent`, etc.). Never raw hex or `rgb(...)`.
2. Both themes are guaranteed to use the **same 24 CSS vars** — no theme-only
   primitive code paths.
3. Shadows: only `shadow-card` / `shadow-elevated` / `shadow-glow`.
4. Animations: respect `prefers-reduced-motion` (already handled in
   `globals.css`).

A pre-commit script (`scripts/check-ui-tokens.mjs`) enforces rule 1.

## Adding a new primitive

1. Create `lib/ui/<name>.tsx`. Keep it ≤150 LOC.
2. Use CVA for variants when there are 2+ visual modes.
3. Forward refs.
4. Re-export from `lib/ui/index.ts`.
5. Add a section to `dashboard/src/app/dashboard/ui-kit/page.tsx` showing all
   variants.

## Migration status

- Phase 0 (this PR): primitives shipped + preview route + token lint.
- Phase 1+: pages migrated off raw `<button>` / `<input>` / `<select>` /
  inline modals. See plan: `~/.windsurf/plans/dashboard-ui-kit-c2d6de.md`.
- Old utility classes (`.btn-*`, `.card`, `.chip-*`, `.has-tooltip`) remain in
  `globals.css` until migration is 100 % complete.
