# Workflow: GateCalibrationWorkflow

## Purpose

Weekly tuning of quality-gate thresholds per niche, using observed
`performance_outcomes`. Runs **Sunday 04:00 UTC**.

## Source

- `src/temporal_workflows/gate_calibration.py`
- Activities: `src/temporal_workflows/gate_activities.py`
  - `list_niches_with_outcomes_activity`
  - `calibrate_gate_for_niche_activity`

## Logic

1. List niches with ≥ N delivered videos and analytics ingested.
2. For each niche, compute per-dimension percentile thresholds (e.g.
   `script_structure_score` p25 of high-CTR videos) and update
   `system_config` keys (`gate_threshold_<niche>_<dimension>`).
3. Records a row in `audit_log` with old vs new thresholds.

## Behaviour without data

If a niche has < `gate_calibration_min_samples` (default 30) outcomes, the
workflow leaves its thresholds untouched and emits a warning log.

## Related pages

- [[Quality-Gates]]
- [[ML-Self-Learning-Loop]]
- [[Schedules]]
