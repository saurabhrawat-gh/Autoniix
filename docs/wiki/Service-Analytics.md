# Service: Analytics

## Purpose

Ingests YouTube Analytics data and mines patterns that feed back into the
self-learning loop. Produces drift signals for the model-maintenance
workflow.

## Port / source

- Port `8008`, memory 512M
- `src/services/analytics/main.py`
- `pattern_miner.py` — mines correlations between script/thumbnail/voice
  features and observed outcomes (retention, CTR, watch time)

## Inputs

- Daily retention curves from `RetentionFetchWorkflow`
- Video-level metrics (views, impressions, CTR, average view duration)
  pulled in `analytics_activity` after each delivery

## Outputs

- `performance_outcomes` rows — the label table for every GBM in the system
- Pattern reports surfaced on the dashboard `/dashboard` home stats and
  Fleet pages.

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /ingest` | Ingest one video’s analytics snapshot |
| `GET  /patterns?niche=` | Mined patterns per niche |
| `GET  /drift?niche=` | Brier / PSI for active models |
| `GET  /retention/{video_id}` | Stored retention curve |

## Related pages

- [[ML-Self-Learning-Loop]] · [[Workflow-RetentionFetch]] · [[Service-Research]]
