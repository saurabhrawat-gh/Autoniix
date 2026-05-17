# ML: Bandits & Experiments

## Purpose

Where GBMs are predictive, **bandits** are decision-making. Thompson
Sampling Beta-Bernoulli bandits choose among arms (hook style, pacing
strategy, intro length, etc.) by treating each arm as an unknown
success-probability and sampling.

## Bandit state

```sql
bandit_state (
  arm_name TEXT, niche TEXT,
  alpha NUMERIC DEFAULT 1.0,  -- prior pseudo-successes
  beta  NUMERIC DEFAULT 1.0,  -- prior pseudo-failures
  updated_at TIMESTAMPTZ
);
```

On each selection, sample `θ ~ Beta(α, β)` for every arm and pick
`argmax(θ)`. On outcome ingest:
- success → `α += 1`
- failure → `β += 1`

A video is a “success” for an arm if it beats the niche’s median CTR or
retention (configurable in `system_config`).

## Active bandits

| Service | Arms |
|---|---|
| research | (n/a — uses GBM ranking) |
| script | `hook_style` × 5, `pacing_strategy` × 4 |
| voice | (n/a) |
| thumbnail | (n/a — ranked by GBM + Vision QC) |

Arms are defined in `system_config` (e.g. `bandit_arms.hook_style`) so
they can be added/removed without code change.

## A/B framework

For coarse-grained experiments (e.g. “TTS provider A vs B”), the bandit
is bypassed and the **A/B framework**
(`src/services/experiments/ab_framework.py`) is used instead:

- Deterministic assignment by `hash(content_id, experiment_name) % 100`
- Outcomes tracked in `experiment_outcomes`
- Welch’s t-test on `GET /experiments/{name}/results`
- Admin-controlled lifecycle (draft → active → paused → completed)

## When to use which

- **Bandit** — many small arms, online learning desired, fast feedback.
- **A/B** — small number of variants, want statistical significance
  before committing.

## Related pages

- [[BFF-Providers-And-Experiments]] · [[ML-GBM-Models]] ·
  [[UI-Experiments-And-Providers]]
