# Autoniix Design System

> **Source of truth.** Every design decision in Autoniix references this document. When a surface diverges, either the surface changes or this doc is updated via `/designer-agent system`.
>
> Owned by: **Designer (UX) Agent** — see `.windsurf/workflows/designer-agent.md`
>
> Status: 🌱 **Seed** — populated incrementally as design passes run. `LOCKED` sections are canon.

---

## How to use this doc
- Designers read end-to-end before every design session (Step 0B of Designer Agent).
- Dev builds to tokens/components — never raw values.
- Updates are proposed as diffs by the Design System Steward and applied only after owner sign-off.

Status tags: `LOCKED`, `EXPERIMENTAL`, `DEPRECATED`.

---

## 1. Principles `LOCKED`

### Design Brand Attributes
Calm · Precise · Intelligent · Premium · Operational · High Trust.
Avoid flashy gradients, excessive glassmorphism, and gaming aesthetics.
References: Linear, Stripe, Vercel, Mercury, Arc Browser, Notion.

### Brand Principles
1. **Typography before decoration.**
2. **Hierarchy before color.**
3. **Information before chrome.**
4. **Motion communicates state.**
5. **One focal point per screen.**

### Product Principles
1. **Trust over delight.** Safe, predictable, honest before charming.
2. **Show the cost.** Costs visible before and after actions.
3. **Status is sacred.** Pipeline state is always accurate, never optimistic.
4. **Calm density.** Dense info with breathing space at decisions.
5. **One vision, many channels.** Adapts to channel branding without cognitive load.
6. **Cinematic output.** Dashboard = utility; video = cinema. See `docs/future/remotion-vision/cinematic-os/`.

---

## 2. Color Tokens `LOCKED`
Token names map 1:1 to Tailwind utilities via `tailwind.config.ts` and to CSS vars in `dashboard/src/app/globals.css`.

- Surfaces: `surface-{0|1|2|3}` (as `bg-surface-*`)
- Foregrounds: `content-{primary|secondary|tertiary|muted|inverse}` (as `text-content-*`)
- Status: `status-{success|warning|error|info}` (as `text/bg/border-status-*`)
- Brand: `accent{,hover,light,muted}` and `secondary{,light}`
- Borders: `border{,hover}`

Light (default) — base `#fcffe1`:
- `surface-bg` #fcffe1  • `surface-sidebar` #eef1cc  • `surface-0` #fafcf0  • `surface-1` #f5f8d8  • `surface-2` #eeecca
- `content-primary` #10100e  • `content-secondary` #3a3e30  • `content-muted` #6a6e60  • `content-disabled` #abaeb0
- `accent-primary-bg` #10100e  • `accent-primary-text` #fcffe1  (inverted — primary button fill)
- `accent-green` #3d5c1a  • `accent-green-hover` #2c4514
- `status-success` #5a8c3a  • `status-warning` #c48a2a  • `status-error` #dc5a3a  • `status-info` #5a7acc
- `border` #d8dca8  • `border-hover` #c4c890

Dark (`.dark`) — base `#10100e`:
- `surface-bg` #10100e  • `surface-sidebar` #141512  • `surface-0` #1e2120  • `surface-1` #252824  • `surface-2` #2a2d28
- `content-primary` #edefd8  • `content-secondary` #bec2ac  • `content-muted` #8c9080  • `content-disabled` #4c5046
- `accent-primary-bg` #fcffe1  • `accent-primary-text` #10100e  (inverted — primary button fill)
- `accent` #fcffe1  • `accent-hover` #edf2c8  • `accent-light` #2c2e26  • `accent-muted` #a0a38a
  — _(Cream replaces moss green; same brand base as light mode surface-bg — 15.1:1 contrast on #10100e. `accent-green` retired.)_
- `status-success` #5a8c3a  • `status-warning` #c48a2a  • `status-error` #dc5a3a  • `status-info` #5a7acc
- `border` #20231e  • `border-hover` #2c2f2a  _(dimmed 2026-06-12 — blends into surface, prevents hard card outlines)_

Additional surface palette (available, placement TBD by visual review):
- `#212922` Charcoal Brown · `#282b28` Graphite — warm olive-toned darks for targeted use

Semantic color scales (50–900 per color, to be expanded in globals.css):
- success, warning, error, info, neutral — every token must have a full 9-step scale.

Rules:
- 90% neutrals, 10% accent usage. Accent reserved for primary CTAs, active nav, and live status only.
- Never use raw hex in components; use token utilities only (enforced by `dashboard/scripts/check-ui-tokens.mjs`).

---

## 3. Typography `LOCKED`
Stack:
- **Primary:** Satoshi Variable (`var(--font-sans)`), system fallbacks — all UI text
- **Secondary:** Inter (`var(--font-secondary)`), fallback for body copy
- **Mono:** JetBrains Mono (`var(--font-mono)`), SF Mono / Menlo fallbacks — code/IDs

> **Migration note:** Codebase currently loads Plus Jakarta Sans. Swap to Satoshi Variable when font assets land.

Scale (CSS vars in `globals.css`; components must reference tokens, not raw values):
- `display-xl` 56px/64 · 700 · tracking -0.025em
- `display-l` 48px/56 · 700 · tracking -0.022em
- `h1` 40px/48 · 700 · tracking -0.022em
- `h2` 32px/40 · 600 · tracking -0.018em
- `h3` 24px/32 · 600 · tracking -0.015em
- `body` 16px/24 · 400 · tracking -0.011em
- `body-sm` 14px/20 · 400 · tracking -0.008em
- `caption` 12px/16 · 400 · tracking 0em
- `metric` 48–64px · 700 · tracking -0.030em — KPI numbers only

Rules:
- Display sizes reserved for hero/landing surfaces only.
- Metric scale used exclusively for KPI card numbers.
- No raw font sizes in components; use token utilities only.

---

## 4. Spacing & Radius `LOCKED`
- Spacing (4px base): `1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 10=40px, 12=48px, 16=64px, 24=96px, 32=128px`
- Never use arbitrary spacing values. Stick to the scale above.
- Radius (Tailwind overrides in code):
  - `none` 0
  - `sm` 4px
  - `md` 6px (default input/badge)
  - `lg` 10px (cards)
  - `xl` 12px
  - `2xl` 16px (modals/sheets)
  - `full` 9999px (pills)

Rules:
- Prefer elevation/tint over heavy borders for grouping.
- Editorial spacing: generous whitespace between sections, compact within components.
- Premium feel = more vertical rhythm, not more decoration.

---

## 5. Elevation & Shadow `LOCKED`
Levels:
- **Level 0 — Flat:** no shadow; `surface-bg` or `surface-sidebar` backgrounds
- **Level 1 — Cards:** `shadow-card` — base card surfaces (subtle 1–3px)
- **Level 2 — Dropdowns/Popovers:** `shadow-elevated` — 8–24px stack
- **Level 3 — Modals/Drawers:** `shadow-elevated` + backdrop blur

Rules:
- Never stack ad-hoc shadows; use one of the 4 levels only.
- Focus uses a ring, not elevation. Hover uses `shadow-card` + tint, active reduces scale 1–2%.
- `shadow-glow` — accent glow for emphasis states only; sparingly.

---

## 6. Motion Tokens `LOCKED`
- Durations: `motion-duration-instant=0`, `fast=120ms`, `base=200ms`, `slow=260ms`, `deliberate=320ms`.
- Easings: `standard=cubic-bezier(0.2,0,0,1)`, `enter=0.12,0,0.1,1`, `exit=0.33,0,0.2,1`, `emphasis=0.16,1,0.3,1`.
- Reduced motion:
  - **Soft** (default): swap translation/scale for opacity + scale-98% using `fast`/`base`.
  - **Hard** (kill switch): `instant` changes (no animation) when user opts in.
- Rules: honor `prefers-reduced-motion`; never use bounce; no infinite animations unless purposeful.
- Implementation: use **Framer Motion** (`motion.*`) for layout/enter/exit; use **Tailwind `transition-*` utilities** for hover/focus/active micro-states; use **CSS `@keyframes`** for loaders/skeletons. Never use JavaScript `setTimeout` for visual timing.

---

## 7. Micro-interactions `LOCKED`
Use these recipes across **all surfaces** (dashboard, modals/drawers, Remotion controls, brand/marketing, emails where applicable). Reference tokens above; do not invent raw values.

### 7.1 Global States
- Hover: subtle tint/elevation `shadow-sm`, duration `fast`, easing `standard`.
- Focus: 2px outline + inner ring, `fast`, `standard`; always visible.
- Active/press: compress 1–2% scale, `fast`, `enter`.
- Disabled: opacity 56%, no shadow, no pointer.
- Loading: skeletons for data regions; spinner only for <800ms waits; otherwise use progress text/bars.
- Success: icon morph to check + accent flash (`fast`, `emphasis`).
- Error: inline message with icon; no shake.

### 7.2 Navigation & Shell
- Route change: 2–3px top progress bar (`base`, `enter`/`exit`) + content skeleton.
- Command palette: scale 98→100% + fade (`fast`, `enter`), exit mirrors.
- Sidebar collapse/expand: width animate `slow`, icons rotate `fast`.
- Breadcrumb/step indicator: slide/fade between steps with tick on completion.

### 7.3 Buttons/Links/CTAs
- Hover: elevate + tint (`fast`).
- Focus: outlined ring.
- Active: compress 1–2%.
- Loading: spinner in-place + text fade; if <800ms use shimmer bar.
- Variants (primary/secondary/ghost/destructive) reuse same states with appropriate tokens.

### 7.4 Forms & Validation
- Inline validation on blur; async validation bar under field (`fast`).
- Field states: hover tint; focus ring; error ring + icon + helper; disabled 56%.
- Submit: optimistic only when safe; else “Saving…” + top progress bar.
- Autocomplete: slide/fade dropdown (`fast`), active option highlight.
- Copy: calm, system-blaming, actionable.

### 7.5 Tables/Lists/Cards
- Row hover tint + divider lift (`fast`).
- Inline actions appear on hover (slide/fade 140ms).
- Selection: checkbox + status dot + row accent.
- Add/remove: slide-fade + scale 98→100% (`fast`).
- Reorder: lift `shadow-md` + smooth settle; no bounce.
- Infinite scroll: row stagger fade (80ms per row).

### 7.6 Steppers, Progress, Status
- Circular stepper with numeric counter; on complete: sweep fill 200ms, tick scale 96→100% 140ms + green shift.
- Inline segmented progress with shimmer (`fast`) for async.
- Counters always paired with text (e.g., “3/7 scenes”).
- Error: amber/red ring + tooltip; no shake.

### 7.7 Modals, Drawers, Popovers
- Modal: translate 12px + fade (`base`, `enter`), backdrop fade 160ms; exit mirrors.
- Drawer: slide from edge (`slow`, `standard`), clamp overshoot.
- Popover/tooltip: scale 98→100% + fade (`fast`).
- Command palette (also): blur-in + scale 98→100% (`fast`).

### 7.8 Feedback (Toasts/Banners/Inline)
- Toast: slide from top (global) or origin corner (context) + auto-dismiss progress line (`base`).
- Inline success: icon + color shift; inline error: icon + retry link.
- Long ops: show ETA or step label; avoid spinner-only states.
- Confirmations: `emphasis` easing + brief accent flash.

### 7.9 Empty/Loading/Error
- Empty: illustration/line/dotted accents + primary CTA + helper copy.
- Loading: skeletons; spinners only for sub-800ms micro waits.
- Error: inline block with icon + retry/view logs; contextual toast optional.
- Partial data: shimmer placeholders.

### 7.10 Search, Filters, Chips
- Filter chip hover/focus/active with smooth color ramp (`fast`).
- Search async: “searching…” micro progress bar.
- Applied filters: pill drop-in/out (slide/fade 120ms) with slight stagger.
- Bulk clear: fade-out all chips stagger 60ms.

### 7.11 Media & Uploads
- Dropzone: dashed/dotted accent pulse on drag-over; per-file progress bars.
- Thumbnails/cards: lazy-load fade + scale 98→100%.
- Audio waveforms: live progress sweep; hover scrub preview.
- Play/pause: icon morph (`fast`).

### 7.12 Video / Remotion Controls
- Scrubber: live time + soft snap; segment markers animate on hover.
- Scene progress: ring per scene with ticks on finalize.
- Captions toggle: fade + brief underline accent.
- Render progress: ring + text + per-step status; completion radial pulse once.

### 7.13 Charts & Data Viz
- Hover tooltips: fade/slide (`fast`); crosshair lines fade in.
- Legend interactions: dim non-selected series (alpha fade 140ms).
- Data refresh: value morph 120–180ms, no bounce.

### 7.14 Lines, Dividers, Accents
- Use 1px hairlines; dotted/dashed accents only for empty/progress contexts.
- Hover lift on divider-adjacent items; prefer elevation/tint over heavy borders.

### 7.15 Copy & Tone
- Direct, calm, cost-transparent; no emojis except playful empty states.
- Status-first phrasing (e.g., “Rendering scene 3 of 7…”).

### 7.16 Accessibility (micro-specific)
- Focus visible everywhere; 44×44px touch on mobile.
- Contrast AA; no color-only cues.
- `prefers-reduced-motion` → soft or hard policy above.
- Screenreader announcements on async completion/errors.

---

### 7.17 Micro-interactions Matrix (screen-level)
Reference tokens from sections 6–7. Apply to all surfaces. Reduce motion per user prefs (soft default, hard kill switch available).

#### Legend
- Durations: `fast=120ms`, `base=200ms`, `slow=260ms`, `deliberate=320ms`.
- Easings: `standard`, `enter`, `exit`, `emphasis` as defined in Motion Tokens.
- Reduced motion: soft = opacity/scale-98% fallback; hard = instant.

#### Auth & Onboarding (page, login, register, forgot/reset-password, accept-invite, onboarding)
| Screen | Event | Behavior | Tokens | A11y |
|---|---|---|---|---|
| Landing/Auth forms | Load | Skeleton for form card; hero fade-in | base, enter | Focus first field; announce page |
| Inputs | Hover/focus/active/error | Tint + ring; error ring + icon + helper; active compress 1–2% | fast, standard | aria-invalid; helper via aria-describedby |
| Submit | Press | If safe optimistic; else "Saving…" + top bar progress | base, enter | Disable + announce busy |
| Success/error | Toast + inline message; no shake | base, emphasis (success) | Announce success/error |
| Password strength | Inline bar grow; color ramp | fast | SR text updates |
| Onboarding steps | Stepper sweep + tick; continue CTA morphs | base, emphasis | Step names in aria-live |

#### Shell & Navigation (dashboard shell, command palette, sidebar, breadcrumbs)
| Screen | Event | Behavior | Tokens | A11y |
|---|---|---|---|---|
| Shell route change | Top 2–3px progress + content skeleton | base, enter/exit | Announce "Loading…" |
| Command palette | Open/close scale 98→100 + fade | fast, enter/exit | Trap focus; ESC closes |
| Sidebar collapse | Width animate; icons rotate | slow/fast | Maintain focus order |
| Breadcrumb/step | Slide/fade, tick on completion | fast | aria-current |

#### Dashboard Home (dashboard/page)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| KPIs/cards | Lazy-load fade+scale | fast | Alt text for icons |
| Quick actions | Hover/active per button spec; inline feedback on trigger | fast/base | Announce start/finish |

#### Content (content, kanban, calendar)
| Screen | Event | Behavior | Tokens | A11y |
|---|---|---|---|---|
| Kanban board | Column drop target pulse; card drag lift shadow-md; drop settle smooth | fast/base | ARIA dnd hints; announce moves |
| Add/remove card | Slide-fade + scale 98→100 | fast | Announce add/remove |
| Inline edit | Field focus ring; save "Saving…" bar | fast/base | SR live region |
| Calendar | Event hover tooltip fade/slide; create modal enter | fast/base | Keyboard create; announce selection |

#### Queue & Jobs (queue, jobs/[id], progress)
| Screen | Event | Behavior | Tokens | A11y |
|---|---|---|---|---|
| Queue rows | Hover tint + inline actions slide/fade | fast | Row describedby status |
| Job detail timeline | Stepper sweep + tick; status chip color shift | base/emphasis | SR announce status change |
| Cancel/retry | Confirm modal enter; inline progress on action | base | aria-live updates |

#### Review (review, review/[id])
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Asset list | Lazy-load thumbnails; hover actions appear | fast | Alt text for thumbnails |
| Approve/reject | Button morph; toast with accent flash; status chip update | fast/emphasis | Announce decision |
| Comment drawers | Slide-in drawer; inline loading for post | base | Focus to textarea |

#### Library (library)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Grid/list toggle | Crossfade + size adjust | fast | Maintain focus |
| Filters/search | Chip drop-in/out stagger; search "searching…" bar | fast | Announce filter changes |
| Empty | Dotted accent + CTA | fast | Describe empty |

#### Channels (channels, channels/new, channels/[id])
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Channel cards/list | Hover tint; select accent; inline actions slide | fast | Announce active channel |
| Create/edit form | Validation per forms spec; submit bar; success check morph | base | SR for errors |
| Delete | Destructive modal enter; confirm accent | base | Focus trap |

#### Providers (providers, providers/[category])
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Catalog tiles | Hover elevate; select highlight; info popover fade | fast | Describe selected provider |
| Connect action | Drawer/modal enter; inline progress | base | Announce connect status |
| Error | Inline block + retry | base | aria-live |

#### Notifications (notifications)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| List rows | Hover lift; unread dot animate on read | fast | Mark read button SR text |
| Filters | Chips animate; bulk clear stagger fade | fast | Announce filter |

#### Workspace/Settings (workspace, settings, settings/flags, profile, users)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Forms/toggles | Standard states; toggles animate thumb | fast | aria-checked |
| Flags | Table hover; inline actions slide; confirm modals | fast/base | SR for toggle |
| Users list | Row hover; role chips animate; invite drawer | fast/base | Announce role change |

#### Progress & Fleet (progress, fleet)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Progress bars | Segmented shimmer; numbers morph | fast/base | aria-valuenow |
| Fleet cards | Status dot pulse for live; hover actions | fast | Live region for status changes |

#### Experiments, Debug (experiments, debug)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Experiment cards | Hover lift; enable toggle animate | fast | SR labels |
| Debug tables/logs | Row hover; copy buttons with inline "Copied" toast | fast | aria-live |

#### UI Kit (ui-kit)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Demo components | Use same recipes; show focus/hover/active visibly | fast/base | Documented props |

#### Uploads/Media (content/library/review)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Dropzone | Dashed/dotted pulse on drag-over; per-file bars | fast | Announce file added |
| Thumbnail load | Fade + scale 98→100 | fast | Alt text |
| Audio preview | Progress sweep; hover scrub preview | fast | SR time updates |

#### Video / Remotion Surfaces (render, review player, jobs)
| Event | Behavior | Tokens | A11y |
|---|---|---|---|
| Scrubber | Soft snap; markers animate on hover | fast | aria-valuenow, valuetext |
| Play/pause | Icon morph | fast | aria-pressed |
| Scene progress | Ring per scene; tick on finalize | base | Announce scene complete |
| Captions toggle | Fade + underline accent | fast | aria-pressed |
| Render complete | Radial pulse once + toast | base/emphasis | SR announcement |

#### Feedback & Toasts (global)
- Toasts slide from top or origin corner; auto-dismiss line; emphasis easing for success.
- Inline errors anchored; no shake.
- Long ops show ETA/step text; avoid spinner-only states.

#### Empty/Loading/Error (global)
- Empty: illustration/lines/dotted accents + CTA + helper.
- Loading: skeletons; spinners only <800ms.
- Error: icon + retry/log link; toast optional.

#### Lines/Dividers/Accents
- 1px hairlines; dotted/dashed reserved for empty/progress cues.
- Divider-adjacent hover lift; prefer elevation/tint over thick borders.

#### Accessibility (global reminder)
- Focus visible; 44×44 touch; contrast AA; no color-only signals.
- `prefers-reduced-motion`: soft fallback; hard kill switch available.
- Announce async completion/errors; aria-current, aria-live, aria-checked as applicable.

---

## 8. Layout Architecture `LOCKED`

### Shell Grid
- **Sidebar:** 240px fixed, collapsible to 56px (icon-only mode)
- **Topbar:** 56px fixed, full width minus sidebar
- **Content area:** max-width 1600px, centered, 12-column responsive grid
- **Content padding:** 32px horizontal, 32px vertical (top of page header)

### Page Structure (every page follows this order)
1. **Page Header** — title (h1/40px), subtitle, page-level actions
2. **Hero KPI** — one dominant metric card (metric scale 48–64px)
3. **Supporting KPIs** — max 3, visually secondary to hero
4. **Operational Metrics** — charts, sparklines, throughput panels
5. **Activity Feed** — real-time chronological event stream
6. **Detailed Data** — tables, queues, lists with inline actions

### Chart Rules
- Minimal grid lines (3 horizontal lines max)
- One primary accent color per chart
- Use sparklines heavily for supporting KPIs
- Line, Area, Bar, Sparkline types only

---

## 9. Navigation `LOCKED`

### Primary Nav — full grouped tree (sidebar, top-to-bottom)

```
1. Home                          /dashboard
2. Studio ▾ (expandable group)   /dashboard/studio
   ├─ Content                    /dashboard/content
   ├─ Review                     /dashboard/review
   ├─ Library                    /dashboard/library
   ├─ Queue / Jobs               /dashboard/queue
   ├─ Fleet                      /dashboard/fleet
   └─ Experiments                /dashboard/experiments
3. Channels                      /dashboard/channels
4. Schedule                      /dashboard/content/calendar
5. Analytics                     /dashboard/analytics
─── (divider) ───────────────────
6. Settings ▾ (expandable group) /dashboard/settings
   ├─ Providers                  /dashboard/providers
   ├─ Users                      /dashboard/users
   └─ Profile                    /dashboard/profile
```

### Nav Rules
- Active item: filled pill background (`surface-1`) + accent-green text + accent-green icon
- Hover: subtle tint (`surface-1`), no heavy border
- Collapsed (icon-only): groups collapse to icon + tooltip on hover reveals label
- Group expand/collapse: chevron rotates 90°; children indent 8px with a 1px left-border connector
- Group dividers: 1px hairline `border` token between logical groups (above Settings)
- Settings group always sits at bottom of sidebar, pinned above user avatar

### Command Palette
- Universal navigation and actions: `⌘K`
- Opens with scale 98→100% + fade (`fast`, `enter`)
- Searches all nav items, recent pages, actions, channels

---

## 10. Components `EXPERIMENTAL`

Component entries use this template:
```
### Component: <Name>
Status: LOCKED | EXPERIMENTAL | DEPRECATED
Anatomy: <parts>
Variants: <list>
Sizes: <list>
States: default / hover / focus / active / disabled / loading / error
Props (canonical): <list>
A11y: <focus, aria, keyboard>
First used in: <issue>
```

### Component: Button
Status: LOCKED
Anatomy: [icon?] + label + [trailing-icon?]
Variants: `primary`, `secondary`, `ghost`, `destructive`
Sizes: `sm` 32px h · `md` 40px h · `lg` 48px h
Radius: `9999px` (full pill) — all variants and sizes
States: default / hover / focus / active / disabled / loading
- **primary:** accent-primary-bg fill + accent-primary-text; inverted (cream on dark, charcoal on light)
- **secondary:** surface-1 bg + border + content-primary text; hover surface-2
- **ghost:** transparent bg + border + content-secondary text; hover surface-1
- **destructive:** status-error bg at 15% opacity + status-error text; hover status-error full bg + white text
A11y: `role=button`, `aria-disabled`, loading → `aria-busy` + spinner, `aria-label` for icon-only

### Component: KPI Card
Status: EXPERIMENTAL
Anatomy: label + metric-value + delta + sparkline
Variants: `hero` (one per page), `supporting` (max 3)
Sizes: hero — unconstrained width; supporting — 1/3 column
States: loading (skeleton), error (inline icon + retry)
- Hero: metric in `metric` scale (48–64px/700), label in `caption`, delta with status color
- Supporting: metric in `h1` scale (40px/700), rest same
Rules: one hero KPI per page. Supporting KPIs visually secondary via size + weight only.

### Component: Input / Form Control
Status: LOCKED
Anatomy: label + [left-icon] + control + [right-slot] + helper/error
Variants: `form` (default), `search`
Sizes:
- `form`: height 44px, radius 8px — used in all forms and settings
- `search`: height 36px, radius 9999px (pill) — used in toolbars and header search
States: default / hover / focus / error / disabled
- **form:** 1px border `border` token; focus: 2px ring `accent-green`; hover: `border-hover`
- **search:** magnifier icon left; clears on ESC; pill radius
- Left icon slot: optional, 16px icon, `content-muted` color
- Right slot: optional (copy, clear, show-password, unit label)
- Error: ring `status-error` + icon + helper text below
- Disabled: opacity 56%, `not-allowed` cursor
- Label: always above field, `caption` scale, `content-secondary` color, never placeholder-only
- Helper text: below field, `caption` scale, `content-muted`
A11y: `aria-invalid`, `aria-describedby` for helper, label always visible

### Component: MultiSelect Tags Input
Status: EXPERIMENTAL
Anatomy: label + [tag-pill…] + text-cursor + dropdown
Variants: `default`, `with-search`
Sizes: min-height 48px, grows vertically as tags are added
States: default / focused / open / error / disabled
- **Tag pill:** `body-sm`, `surface-1` bg, `border` border, `content-primary` text, `×` dismiss icon right
- **Focused:** outer 2px ring `accent`; dropdown opens below with full shadow-elevated
- **Dropdown:**
  - Search field at top (`search` input variant, 40px h)
  - Checkbox list below; checked items highlighted with `accent-light` bg
  - Already-selected items show check; keyboard-navigable
  - Selected tags appear inside the input field as pills
- **Tag dismiss:** `×` on each pill removes it; backspace on empty cursor removes last tag
- Max visible rows in dropdown: 6; scroll after
A11y: `role=combobox`, `aria-multiselectable=true`, tags have `role=option aria-selected=true`, `aria-label` on dismiss button

### Component: URL Input (with Prefix)
Status: EXPERIMENTAL
Anatomy: prefix-badge + input
Sizes: height 48px
States: default / focus / error
- Prefix badge: `surface-2` bg, `content-muted` text, left-attached, 1px right border `border`
- Input right section: editable slug value only
- Focus ring wraps entire control (prefix + input together)
- Error: ring `status-error` on input section only
Used in: workspace creation onboarding

### Component: Toggle / Switch
Status: LOCKED
Anatomy: track + thumb + [label + description]
Sizes: track 44×24px, thumb 20×20px
Variants: `inline` (widget only), `row` (full-width: label+desc left, toggle right — like iOS Settings)
States: off / on / disabled
- Off: `surface-2` track, `content-primary` thumb
- On: `accent-green` track, white thumb; thumb slides right 200ms `standard`
- Focus: 2px ring around track
- Label: `body-sm` right of control (inline) or left (row)
- Row variant: description text `caption` `content-muted` below label
A11y: `role=switch`, `aria-checked`

### Component: Table
Status: EXPERIMENTAL
Anatomy: sticky-header + rows + pagination
Variants: `default`, `dense`, `with-bulk-actions`
States: row-hover (tint), row-selected (accent tint + checkbox), loading (skeleton rows)
- Sticky header with `surface-0` + `shadow-card`
- Inline row actions appear on hover (slide/fade 140ms)
- Bulk action bar slides in from bottom on selection
- Column personalization: hidden/shown per user preference
A11y: `role=grid`, column headers `scope=col`, keyboard navigation

### Component: Badge / Status Chip
Status: EXPERIMENTAL
Anatomy: dot? + label
Variants: `success`, `warning`, `error`, `info`, `neutral`, `accent`
Sizes: `sm` (12px text) · `md` (13px text)
- Background: status color at 10% opacity; text: status color (full)
- Live/pulsing: animated dot for real-time states

### Component: Card
Status: EXPERIMENTAL
Anatomy: header + body + footer?
Variants: `flat`, `elevated`, `interactive`
Sizes: unconstrained; uses container width
States: default / hover (interactive only) / loading
- `flat`: no shadow, `surface-0` bg
- `elevated`: `shadow-card`, `surface-0` bg
- `interactive`: `shadow-card` + hover tint + cursor-pointer

### Component: Dialog / Modal
Status: LOCKED
Anatomy: overlay + panel [header + body + footer]
Variants: `default`, `destructive`
Sizes:
- `sm` 360px centered — destructive confirmations, short alerts
- `md` 480px centered — standard forms, settings panels
- `lg` 720px centered — complex forms, multi-step
- `xl` drawer — 560px wide, full viewport height, slides from right
States: open / closed / loading
- Backdrop: `rgba(0,0,0,0.5)` — no blur (performance)
- sm/md/lg: translate 12px + fade (`base`, `enter`); centered both axes
- Drawer: slides from right edge (`slow`, `standard`)
- Radius: 12px (sm/md/lg panel); 0 (drawer)
- Enter: translate 12px + fade (`base`, `enter`)
- Exit: reverse
A11y: focus trap, `role=dialog`, `aria-labelledby`, ESC closes

### Component: Delete Dialog
Status: LOCKED
Anatomy: icon (status-error tinted box) + title + description + [Cancel ghost] + [Delete destructive]
Size: `sm` (360px)
- Icon: trash/warning in a 40×40px rounded box with status-error at 15% opacity
- Title: bold, `h3` scale, `content-primary`
- Description: `body-sm`, `content-muted`
- Buttons: right-aligned, Cancel ghost + Delete destructive

### Component: Toast / Notification
Status: LOCKED
Anatomy: icon + message + [action] + close
Variants: `success`, `error`, `warning`, `info`
Sizes: fixed width 360px, pill radius
Placement: bottom-right corner, 16px from edge
- Slides up on enter (`base`, `enter`); fade on exit
- Auto-dismiss after 4s; manual close × button
- Stack max 3; oldest dismissed first; 8px gap between toasts
A11y: `role=alert` or `role=status`; `aria-live`

### Component: Skeleton Loader
Status: LOCKED
Anatomy: shaped placeholder matching content layout
Variants: `text`, `card`, `table-row`, `kpi`
Animation: **pulse** (opacity fade in/out between `surface-1` and `surface-0`; no shimmer)
- `@keyframes pulse` — opacity 1 → 0.4 → 1, 1.5s infinite
- Always show for data regions; spinner only for <800ms micro waits
- Radius matches the target element's radius

### Component: Avatar
Status: LOCKED
Anatomy: circular image + initials fallback
Sizes: `sm` 24px · `md` 32px · `lg` 40px
- Image: circular crop
- Fallback: `surface-1` bg + `content-secondary` text — first 1–2 initials of display name
A11y: `alt` text with user display name

### Component: Badge
Status: LOCKED
Anatomy: [dot?] + label
Variants: `success`, `warning`, `error`, `info`, `neutral`
Sizes: 20–24px height, pill radius, `caption` (12px) text
- Fill: status color at 15% opacity; text: status color (full)
- Dot variant: 6px circle dot left of label

### Component: Checkbox
Status: LOCKED
Anatomy: control + label
Sizes: 20×20px control, 4px radius
- Unchecked: `surface-1` bg + 1px border `border`
- Checked: `accent-green` fill + white checkmark SVG
- Focus: 2px ring `accent-green`
- Disabled: opacity 56%
A11y: `role=checkbox`, `aria-checked`

### Component: Select
Status: LOCKED
Anatomy: label + trigger + dropdown panel
Sizes: 44px trigger height, 8px radius
States: default / hover / open / disabled
- Trigger: same styling as form input + chevron icon right
- Dropdown panel: `surface-0` bg, 12px radius, 1px border, `surface-1` hover rows
- Max visible rows: 6; scroll after
A11y: `role=combobox`, keyboard navigable

### Component: Tabs
Status: LOCKED
Anatomy: tab list + tab panels
Variants: single (pill/filled active)
- Active tab: `surface-1` bg fill, `content-primary` text
- Inactive tab: transparent, `content-secondary` text; hover `surface-1`
- Tab list container: `surface-0` bg, 8px radius, p-1 padding
- Tab item: pill shape, height 32px, px-12px
A11y: `role=tablist`, `role=tab`, `aria-selected`, keyboard left/right navigation

### Component: Tooltip
Status: LOCKED
Anatomy: trigger + floating content
Sizes: 8px radius, max-width 200px
- Delay: 300ms on hover entry; instant on exit
- `surface-2` bg, `content-primary` text, `caption` scale
- Auto-positions above/below/left/right based on available space
- Arrow pointing to trigger element
A11y: `role=tooltip`, `aria-describedby` on trigger

### Component: KPI Card
Status: LOCKED
Anatomy: icon-box + metric-value + label + delta-badge
Variants: `hero` (one per page), `supporting` (max 3)
- Icon box: 36×36px, 8px radius, `surface-1` bg, `accent-green` icon
- Metric: `metric` scale (48–64px for hero; 32–40px for supporting), `content-primary`
- Label: `caption`, `content-secondary`
- Delta badge: `↑ 12%` or `↓ 3%` — `status-success` or `status-error` filled pill badge
- Card: `surface-0` bg, 12px radius, 1px border `border`
States: loading (skeleton), error (inline icon + retry)

### Component: Table Row
Status: LOCKED
Anatomy: cells + [checkbox] + inline-actions
Sizes: 48px height per row
- Default: `surface-0` bg, 1px `border` bottom separator
- Hover: `surface-1` bg
- Inline actions: appear on row hover (slide/fade 140ms), positioned right

### Component: Empty State
Status: LOCKED
Anatomy: [icon/illustration] + heading + description + [CTA button]
- Centered in content area (both axes)
- Icon: 48×48px, `content-muted` color; or custom SVG illustration per context
- Heading: `h3` scale, `content-primary`
- Description: `body-sm`, `content-muted`
- CTA: primary button

---

## 11. Patterns `EXPERIMENTAL`
Patterns document multi-component solutions.

### Pattern: Destructive Confirmation
- Trigger button: `destructive` variant
- Dialog: `destructive` variant with red accent header
- Confirm input: type resource name to enable confirm button
- Cancel: `ghost`; Confirm: `destructive primary`

### Pattern: Inline Cost Preview
- Show estimated cost before action (e.g. "~\$0.012 per render")
- Use `caption` scale + `content-muted` color
- After action: show actual cost diff

### Pattern: KPI Hero + Supporting Grid
```
┌──────────────────────────────────────────────────────┐
│  HERO KPI (full width or 60% col)                    │
│  48px metric  +delta  sparkline                      │
├──────────────┬───────────────┬───────────────────────┤
│ Supporting 1 │ Supporting 2  │ Supporting 3           │
│ 32px metric  │ 32px metric   │ 32px metric            │
└──────────────┴───────────────┴───────────────────────┘
```

### Pattern: Provider Health Row
- Provider logo + name + status badge + latency sparkline + cost/1k tokens + fallback order pill
- Inline actions: test, configure, disable

### Pattern: Activity Feed Row
- Timestamp (caption/muted) + event icon (status-colored) + message (body-sm) + resource link
- Real-time: new rows slide in from top
- Empty: dotted accent + "No recent activity" + CTA

### Pattern: Empty State
- Always show: illustration/icon + title (h3) + helper copy (body-sm) + primary CTA
- Never show a blank screen
- Recommended next action must be obvious

### Pattern: AI Workflow Components
- **Pipeline Builder:** drag-drop chain of provider → prompt → validation → output blocks
- **Agent Chain:** visual node graph; each node shows status + cost
- **Provider Routing:** priority-ordered list with fallback indicators
- **Prompt Blocks:** code-font editor with syntax highlight + token counter
- **Validation Steps:** checklist with pass/fail indicators

### Pattern: Workspace Onboarding (Welcome Flow)

**URL Routing:**
```
Primary:   dash.autoniix.com/[workspace_slug]/welcome
```
- `workspace_slug` = lowercase, hyphenated workspace name (e.g. `my-brand`)
- Route is workspace-scoped; redirects to `/[workspace_slug]/overview` after completion
- Each workspace has its own `/welcome` — revisitable for setup completion

**Step sequence — 4 steps (AI Provider step removed):**
```
Step 1 — Workspace  (no back, no skip)
  └ Workspace name (form input, 44px)
  └ URL slug (URL prefix input, prefix: "dash.autoniix.com/")
  └ [Create workspace] primary button (full-width, lg=48px, pill)

Step 2 — Profile  (← Back top-left, Skip top-right)
  └ Avatar upload circle (80×80px click area)
  └ Display name (form input, pre-filled)
  └ Title/Role (form input, placeholder "Content strategist…")
  └ [Skip] ghost + [Continue →] primary

Step 3 — Channel  (← Back top-left, Skip top-right)
  └ YouTube OAuth connect card (platform icon + name + [Connect] button)
  └ [Skip for now] ghost + [Connect →] primary

Step 4 — Done  (no back, no skip)
  └ Checklist of completed steps (✓ Workspace, ✓ Profile, ✓ Channel)
  └ [Go to dashboard →] primary CTA (full-width)
```

**Progress indicator:**
- Labelled step tabs: `Workspace / Profile / Channel / Done`
- Active tab = current step (filled pill active state)
- Completed tabs visually marked

**Layout rules:**
- Pure `surface-bg` background (no sidebar/topbar)
- Centered card: 480px wide, `surface-0` bg, 12px radius, 1px border `border`; no shadow
- ← Back top-left on steps 2–3; Skip top-right on steps 2–3
- Fonts: heading `h2` (32px/600), body `body-sm` (14px)

**Motion:**
- Step transition: slide + fade from right (`base`, `enter`); back = reverse
- Card entrance: scale 96→100% + fade (`base`, `enter`)
- Step tab: fill transition on advance

---

## 12. Voice & Tone `LOCKED`
- Plain English (Grade ~8 unless technical audience).
- Direct verbs in CTAs.
- Honest about state and cost.
- Calm under errors; name the failing system + next action.
- Minimal emojis (only playful empty states).
- Names are sacred; use user-provided names, not IDs.

---

## 13. Brand Identity `TBD`
- Logo, logomark, brand colors, channel branding system: TBD.

---

## 14. Video Output Visual Language `TBD`
Source: `docs/future/remotion-vision/cinematic-os/`. Will include scene composition, title typography, transitions, music envelope, safe areas, captions, thumbnail relationship.

---

## 15. Accessibility Floor `LOCKED`
- WCAG AA contrast; focus visible; screenreader labels on icon-only controls.
- 44×44px touch targets on mobile.
- `prefers-reduced-motion` honored.
- Form errors associated with their field; no color-only info.

---

## 16. Deprecations
| Token / Component | Replaced by | Sunset by | Notes |
|---|---|---|---|
| (empty) | | | |

---

## Changelog
| Date | Change | Author | Issue |
|---|---|---|---|
| 2026-05-24 | Initial seed + micro-interactions | Designer Agent | — |
| 2026-06-10 | Reference docs ingested: typography→Satoshi Variable, color tokens aligned to vision, brand principles locked, layout/nav/components/patterns seeded | Designer Agent | AE-17 |
| 2026-06-11 | Full Designer Agent session — v1 spec locked: bg #10100e/#fcffe1, warm-tinted status colors, moss green accent, inverted primary button, pill buttons, all component specs agreed, 4-step onboarding | Designer Agent | AE-326 |
