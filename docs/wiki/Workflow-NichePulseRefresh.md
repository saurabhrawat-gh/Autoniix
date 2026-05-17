# Workflow: NichePulseRefreshWorkflow

## Purpose

Weekly refresh of trend signals per niche. **Sunday 05:00 UTC**.

## Source

- `src/temporal_workflows/niche_pulse.py`
- Activities: `src/temporal_workflows/niche_pulse_activities.py`
  - `refresh_niche_pulse_activity`

Uses `list_niches_with_outcomes_activity` from `gate_activities.py` so the
two workflows share the same niche census.

## What it does

For each active niche, calls the research service to:

- Pull fresh Google Trends + YouTube autocomplete + YouTube trending.
- Recompute burst scores via `burst_detector.py` (rolling z-score).
- Refresh competitor outlier set (`competitor_insights.py`).
- Mine new phrases from competitor titles, score for novelty, append to
  `phrase_bank`.
- Update `trend_signals` and bump per-niche freshness timestamps in
  `system_config`.

## Why it matters

The research opportunity scorer weighs `freshness`, `trend_momentum`,
`phrase_novelty` and `burst_score` — all of which are stale without this
workflow. After the first deploy run
`refresh_niche_pulse_activity` manually per niche (see
`PENDING.md` first-deploy-checklist) to seed the tables.

## Related pages

- [[Service-Research]]
- [[ML-Self-Learning-Loop]]
- [[Schedules]]
