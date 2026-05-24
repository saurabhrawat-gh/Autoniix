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
1. **Trust over delight.** Safe, predictable, honest before charming.
2. **Show the cost.** Costs visible before and after actions.
3. **Status is sacred.** Pipeline state is always accurate, never optimistic.
4. **Calm density.** Dense info with breathing space at decisions.
5. **One vision, many channels.** Adapts to channel branding without cognitive load.
6. **Cinematic output.** Dashboard = utility; video = cinema. See `docs/remotion-vision/cinematic-os/`.

---

## 2. Color Tokens `TBD`
Naming:
- Surfaces: `bg-surface-{0|1|2|3}`
- Foregrounds: `text-fg-{default|muted|emphasis|inverse}`
- Status: `bg-status-{success|warning|danger|info}`, `text-status-*`, `border-status-*`
- Brand: `bg-brand-{primary|accent}`, `text-brand-*`
- Channel-scoped: `bg-channel-accent`
Raw values: TBD.

---

## 3. Typography `TBD`
- Display: `text-display-{xl|lg|md}`
- Heading: `text-h-{1|2|3|4}`
- Body: `text-body-{lg|md|sm|xs}`
- Mono: `text-mono-{md|sm}`
Stack: TBD.

---

## 4. Spacing & Radius `TBD`
- Spacing: `space-{0|1|2|3|4|5|6|8|10|12|16|20|24}` on 4px base
- Radius: `radius-{none|sm|md|lg|xl|full}`

---

## 5. Elevation & Shadow `TBD`
- Shadows: `shadow-{none|sm|md|lg|xl}` for cards, popovers, modals, palette.

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

## 8. Components `TBD`

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

---

## 9. Patterns `TBD`
Patterns (recipes) will document multi-component solutions like destructive confirmation, inline cost preview, channel switcher, render progress strip.

---

## 10. Voice & Tone `LOCKED`
- Plain English (Grade ~8 unless technical audience).
- Direct verbs in CTAs.
- Honest about state and cost.
- Calm under errors; name the failing system + next action.
- Minimal emojis (only playful empty states).
- Names are sacred; use user-provided names, not IDs.

---

## 11. Brand Identity `TBD`
- Logo, logomark, brand colors, channel branding system: TBD.

---

## 12. Video Output Visual Language `TBD`
Source: `docs/remotion-vision/cinematic-os/`. Will include scene composition, title typography, transitions, music envelope, safe areas, captions, thumbnail relationship.

---

## 13. Accessibility Floor `LOCKED`
- WCAG AA contrast; focus visible; screenreader labels on icon-only controls.
- 44×44px touch targets on mobile.
- `prefers-reduced-motion` honored.
- Form errors associated with their field; no color-only info.

---

## 14. Deprecations
| Token / Component | Replaced by | Sunset by | Notes |
|---|---|---|---|
| (empty) | | | |

---

## Changelog
| Date | Change | Author | Issue |
|---|---|---|---|
| 2026-05-24 | Initial seed + micro-interactions | Designer Agent | — |
