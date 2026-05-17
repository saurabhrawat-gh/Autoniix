# BFF: Providers & Experiments

## Purpose

Manage provider credentials (LLM/TTS/image/search/storage) and run A/B
experiments across them or any other tunable parameter.

## Source

- `src/services/dashboard/v2/providers.py:1-1300` — the heaviest BFF module
- `src/services/dashboard/v2/experiments.py:1-100`
- `src/services/experiments/ab_framework.py`

## Providers endpoints (`/api/v2/providers/...`)

| Method + Path | Role | Purpose |
|---|---|---|
| `GET    /providers/{category}` | admin+ | List configured providers, priorities, enabled flags |
| `POST   /providers/{category}` | admin+ | Add credential |
| `PUT    /providers/{category}/{id}` | admin+ | Update credential or priority |
| `DELETE /providers/{category}/{id}` | admin+ | Remove |
| `POST   /providers/{category}/{id}/test` | admin+ | Live health-check using the credential |
| `POST   /providers/{category}/reorder` | admin+ | Reorder fallback chain |

All writes invalidate `ProviderRegistry._instances` via
`src/providers/invalidation.py` so the next service call re-resolves.

## Experiments endpoints (`/api/v2/experiments/...`)

| Method + Path | Role | Purpose |
|---|---|---|
| `GET  /experiments` | admin+ | List |
| `POST /experiments` | admin+ | Create `{name, variants:[{key,weight}]}` |
| `POST /experiments/{name}/activate` | admin+ | Begin assignment |
| `POST /experiments/{name}/pause`    | admin+ | Stop new assignments |
| `POST /experiments/{name}/complete` | admin+ | Lock results |
| `GET  /experiments/{name}/results`  | admin+ | Welch’s t-test significance |

Assignment is deterministic by hash of `(content_id, experiment_name)` so
the same video always falls in the same variant.

## Outcome tracking

The workflow emits an `experiment_outcome` for each completed video,
tagging the variant key and the metric (CTR, retention, watch time).
`results` aggregates and runs the t-test.

## Related pages

- [[Architecture-Provider-Pattern]] · [[ML-Bandits-And-Experiments]] ·
  [[UI-Experiments-And-Providers]]
