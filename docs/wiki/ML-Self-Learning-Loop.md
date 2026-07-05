# ML: Self-Learning Loop

## Purpose

Close the loop between produced videos, observed YouTube performance,
and future production decisions.

## Stages

```
 produce video
     │
     ▼
 persist features (research_features, script_features, ...)
     │
     ▼
 deliver  →  retention-fetch  →  performance_outcomes
                                      │
                                      ▼
                          weekly: model-maintenance
                                      │
                                      ▼
                          retrain niche GBMs + bandit updates
                                      │
                                      ▼
                          next video picks better defaults
```

## Outcome ingest

The analytics service receives the daily retention curve plus
video-level metrics (CTR, average view duration) and writes one row
to `performance_outcomes` per video. Each predictor service exposes
`POST /<service>-feedback` which the workflow calls in the analytics
phase.

## Retraining

For each `(model, niche)`:

1. Pull rows from `performance_outcomes` joined to the matching
   features table.
2. Time-weight (recency bias α = 0.05 / week).
3. Fit GBM + isotonic calibrator.
4. Hold-out 20% for validation, compute Brier + AUC + PSI vs the
   previous version’s holdout.
5. Only activate (flip `ml_models.active`) if Brier doesn’t regress.

## Drift detection

Population Stability Index (PSI) > 0.25 on features and Brier > 0.30
mark a model **drifted**. The fleet page surfaces this; ops can
manually retrain or wait for the weekly schedule.

## Cold start

New niches use either:
- Synthetic data from `scripts/generate_training_data.py`
- A cross-niche prior (planned, deferred under
  `cross-niche-transfer-learning` in `docs/future/PENDING.md`)

Until a niche has ≥ `gate_calibration_min_samples` (30) outcomes, the
calibrator falls back to fleet-wide tier labels.

## Cost savings

`intelligence_metrics.cost_usd` records how often a local decision
replaced an LLM call. Estimated savings $0.03–0.05/video, surfaced on
the Settings page via `GET /intelligence/savings`.

## Related pages

- [[ML-GBM-Models]] · [[Workflow-ModelMaintenance]] ·
  [[Workflow-RetentionFetch]] · [[Service-Analytics]]
