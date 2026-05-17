# ML: GBM Models

## Purpose

Four gradient-boosted models predict per-niche outcomes and feed
decisions back into the pipeline.

## Models

| Name | Service | Predicts | Used to |
|---|---|---|---|
| `research_gbm` | research | Performance score (CTR × retention) | Rank candidate topics |
| `script_gbm` | script | Retention curve under-area | Decide rewrites + bandit arms |
| `voice_style_gbm` | voice | Audio-quality score | Pick TTS knob settings per niche |
| `thumbnail_ctr_gbm` | thumbnail | CTR percentile | Score / rank variants alongside Vision QC |

## Algorithm

sklearn `GradientBoostingClassifier` with **isotonic calibration**
(`CalibratedClassifierCV(method="isotonic")`) so predicted probabilities
are well-calibrated for thresholding. Each model is per niche (a
“finance” model is distinct from a “sleep” model) which lets the system
learn niche-specific feature importances.

## Persistence

Blobs stored in the `ml_models` (research, voice, thumbnail) and
`script_models` (script) tables along with metadata:

```sql
ml_models (
  model_name TEXT, niche TEXT, version INT,
  blob BYTEA,         -- joblib.dumps
  metrics JSONB,      -- {brier, auc, n_samples, weighted_fraction}
  trained_at TIMESTAMPTZ,
  active BOOLEAN
);
```

Only one row per `(model_name, niche)` is `active=TRUE`. The retrain
workflow only flips active to a new version if the validation metrics
improve (no regression in Brier).

## Retraining cadence

- Weekly via `ModelMaintenanceWorkflow` (Sun 06:00 UTC).
- Manual: `POST /<service>/train { niche }` per service.
- Trigger override: sample count grew > 20% since last train.

## Health surface

`model_health` table is read by the Fleet page. Columns:
`brier`, `psi`, `last_check`, `healthy`. Brier < 0.20 is the “healthy”
target; PSI > 0.25 signals drift.

## Synthetic bootstrapping

`scripts/generate_training_data.py` generates 60+ realistic rows per
niche per table for cold-start. Niche profiles: tech, health, finance,
education, entertainment. Outcomes are correlated with features so the
first-train model is at least directionally correct.

## Related pages

- [[Workflow-ModelMaintenance]] · [[ML-Self-Learning-Loop]] ·
  [[ML-Bandits-And-Experiments]] · [[Service-Research]]
