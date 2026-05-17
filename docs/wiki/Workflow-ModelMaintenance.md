# Workflow: ModelMaintenanceWorkflow

## Purpose

Weekly ML model housekeeping. **Sunday 06:00 UTC** (after gate-calibration
and niche-pulse so it sees fresh outcomes).

## Source

- `src/temporal_workflows/model_maintenance.py`
- Activities: `src/temporal_workflows/model_activities.py`
  - `check_model_freshness`
  - `check_model_drift`
  - `retrain_model`
  - `update_model_health_activity`

## Trainable models

```python
TRAINABLE_MODELS = [
    "voice_style_gbm",     # voice service
    "thumbnail_ctr_gbm",   # thumbnail service
    "research_gbm",        # research opportunity scorer
    "script_gbm",          # script self-learning
]
```

For each model × niche pair:

1. `check_model_freshness` — if `trained_at` older than threshold or sample
   count grown by > 20%, mark for retrain.
2. `check_model_drift` — PSI / Brier on a hold-out window; flag drift.
3. `retrain_model` — calls the owning service’s `/train` endpoint which
   fits a `GradientBoostingClassifier` + isotonic calibration on
   `performance_outcomes`. Stores binary blob + metadata to `ml_models`
   table; activates only if validation metrics improve.
4. `update_model_health_activity` — writes status + metrics to
   `model_health` table (visible on the Fleet dashboard).

## Failure isolation

Each `(model, niche)` runs as an independent activity with
`RETRY_STANDARD`. A retrain failure for one niche does not abort the
workflow.

## Related pages

- [[ML-GBM-Models]]
- [[ML-Self-Learning-Loop]]
- [[Schedules]]
