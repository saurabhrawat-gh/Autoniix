# Quality Gates

## Purpose

Thirty-plus quantitative gates checked after every phase. Below-threshold
triggers rewrites/regeneration/human review depending on the gate.

## Source

- `docs/architecture/05-QUALITY-GATES.md` (long-form)
- `src/quality/` (scoring helpers)
- `src/temporal_workflows/video_production.py:190-240` (threshold tables)

## Default thresholds

| Dimension | Threshold |
|---|---|
| `research_depth_score` | 8.0 |
| `script_structure_score` | 9.0 |
| `hook_retention_score` | 9.0 |
| `voice_quality_score` | 8.0 |
| `thumbnail_score` | 9.0 |
| `direction_score` | 8.5 |
| `production_score` | 8.0 |
| `composite_score` | 8.5 |

In test mode every threshold is forced to 0 so the pipeline runs end to end.

## Phase actions on failure

| Phase | Action |
|---|---|
| Script | LLM critique-and-rewrite up to **3** times targeting 9.0 |
| Thumbnail | Regenerate variants with refined prompt up to **2** times |
| Voice | Re-synthesise the failing segment with adjusted prosody |
| Assets | Escalate from stock to DALL·E |
| Direction | LLM rewrite up to 2 times |
| Final composite | If within 0.5 of threshold → `awaiting_review` (human gate) |

## Calibration

Thresholds are tuned weekly by `GateCalibrationWorkflow`, written back to
`system_config` keys like `gate_threshold_<niche>_<dimension>`. Niche-specific
thresholds override the defaults above.

## Composite score

Weighted mean of per-dimension scores; weights live in
`system_config.composite_weights` and can be tuned per niche.

## Human-review path

When score is within `composite_review_window` (default 0.5) of the
threshold:

1. Workflow sets status `awaiting_review`.
2. UI lists the video on `/dashboard/review`.
3. Operator approves / rejects / requests changes.
4. Workflow resumes accordingly.

## Related pages

- [[Workflow-VideoProduction]] · [[Workflow-GateCalibration]] ·
  [[UI-Queue-And-Review]]
