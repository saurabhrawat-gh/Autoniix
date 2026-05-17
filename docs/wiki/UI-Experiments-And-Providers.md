# UI: Experiments & Providers

## Routes

| Route | File |
|---|---|
| `/dashboard/experiments` | `experiments/page.tsx` |
| `/dashboard/providers` | `providers/page.tsx` |
| `/dashboard/providers/[category]` | `providers/[category]/page.tsx` |

## Experiments

List of A/B experiments with status pills (draft, active, paused,
completed). Each row shows variants, weights, assignment count, and the
current best-performing variant with significance (Welch’s t-test
p-value from `GET /experiments/{name}/results`).

Actions per row: **Activate**, **Pause**, **Complete**, **View results**.

Create dialog: name + variants `[{key, weight}]` + outcome metric
(CTR / retention / watch_time / composite_score).

## Providers

Master page listing every category (LLM, TTS, Image, Search, Storage,
Secrets) with credential counts. Click into a category for its detail
page:

- Drag-to-reorder fallback chain (`POST /providers/{cat}/reorder`).
- Add credential dialog (API key, optional label, channel scope).
- Per-credential controls: enable/disable, edit, delete, **Test**
  (live `health_check`).

Saving any change calls `invalidate_category(category)` on the BFF so
running services pick up the new chain on their next provider lookup.

## Related pages

- [[BFF-Providers-And-Experiments]] · [[Architecture-Provider-Pattern]] ·
  [[ML-Bandits-And-Experiments]]
