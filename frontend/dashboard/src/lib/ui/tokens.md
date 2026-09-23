# Design Tokens

All Autoniix UI primitives reference these CSS variables. They are defined in
`dashboard/src/app/globals.css` under `:root, .dark`. Autoniix ships a single
dark theme (shared with the marketing site); `<html>` always carries
`class="dark"` so `dark:` utilities remain valid. The "Light" columns below are
historical and no longer rendered.

> **Rule:** Primitives in `lib/ui/*` must never use raw hex or `rgb(...)`
> literals — only token classes (`bg-surface-0`, `text-content-primary`, etc.).
> Enforced by `scripts/check-tokens.mjs`.

## Surfaces (background layers)

| Token       | Light         | Dark       | Use                               |
| ----------- | ------------- | ---------- | --------------------------------- |
| `surface-0` | `255 255 255` | `30 32 38` | Cards, dropdown menus, dialogs    |
| `surface-1` | `247 248 249` | `37 39 45` | Page background                   |
| `surface-2` | `240 241 242` | `48 49 55` | Hover, subtle fills, tab strips   |
| `surface-3` | `224 225 227` | `58 59 64` | Pressed, archived, disabled fills |

## Brand

| Token             | Light         | Dark         |
| ----------------- | ------------- | ------------ |
| `accent`          | `0 151 111`   | `0 216 159`  |
| `accent-hover`    | `0 65 48`     | `77 228 188` |
| `accent-light`    | `230 249 244` | `0 71 81`    |
| `accent-muted`    | `77 228 188`  | `0 151 111`  |
| `secondary`       | `71 48 135`   | `102 69 193` |
| `secondary-light` | `240 236 249` | `31 21 58`   |

## Text

| Token               | Light         | Dark          |
| ------------------- | ------------- | ------------- |
| `content-primary`   | `30 32 38`    | `255 255 255` |
| `content-secondary` | `67 68 73`    | `210 210 212` |
| `content-tertiary`  | `120 121 125` | `156 157 160` |
| `content-inverse`   | `255 255 255` | `30 32 38`    |

## Borders

| Token          | Light         | Dark       |
| -------------- | ------------- | ---------- |
| `border`       | `224 225 227` | `58 59 64` |
| `border-hover` | `210 210 212` | `67 68 73` |

## Status

| Token            | Light        | Dark         |
| ---------------- | ------------ | ------------ |
| `status-success` | `0 120 47`   | `77 197 123` |
| `status-warning` | `161 83 5`   | `252 193 95` |
| `status-error`   | `162 22 22`  | `239 99 99`  |
| `status-info`    | `11 104 179` | `16 148 255` |

## Shadows

`--shadow-card`, `--shadow-elevated`, `--shadow-glow` — all exposed as Tailwind
`shadow-card`, `shadow-elevated`, `shadow-glow`.

## Radii

Tailwind `rounded-*` is overridden in `tailwind.config.ts`:
`sm` 6 / default 8 / `lg` 10 / `xl` 12 / `2xl` 14.

## Usage in Tailwind

Every token is exposed as a Tailwind color utility:

```tsx
<div className="bg-surface-0 text-content-primary border border-border" />
<button className="bg-accent text-content-inverse hover:bg-accent-hover" />
<span className="text-status-error" />
```

Use `<color>/<alpha>` for opacity (works because of `<alpha-value>` in
`tailwind.config.ts`):

```tsx
<div className="bg-accent/10 text-accent" />
```
