# Service: Research

## Purpose

Topic discovery and opportunity scoring. Combines free trend sources,
competitor analysis, semantic similarity dedup, and a per-niche GBM that
predicts performance. Runs entirely local except optional Google Trends.

## Port / source

- Port `8001`, memory 1536M
- `src/services/research/main.py:1-1000` — FastAPI app, ~12 endpoints
- Intelligence modules under `src/services/research/`:
  - `trend_collector.py` — Google Trends (pytrends) + YouTube autocomplete + trending
  - `competitor_insights.py` — YouTube Data API, outlier 3–10× avg
  - `similarity.py` — SBERT all-MiniLM-L6-v2 + pgvector + SimHash
  - `opportunity_scorer.py` — 9-feature weighted scorer
  - `burst_detector.py` — rolling z-score + n-gram mining
  - `saturation.py` — niche saturation index
  - `self_learning.py` — GBM + Thompson Sampling bandits

## Endpoints (selected)

| Method + Path | Purpose |
|---|---|
| `POST /research` | Full pipeline: trends → candidates → dedup → score → top-N |
| `GET  /trends?niche=` | Raw trend signals |
| `GET  /competitors?channel_id=` | Outliers from competitor set |
| `GET  /bursts?niche=` | Phrases bursting this week |
| `GET  /phrases?niche=` | Phrase bank |
| `POST /similarity` | Check if a topic duplicates an existing one |
| `POST /feedback` | Ingest performance outcome for a delivered video |
| `POST /train`  | Retrain niche GBM |
| `GET  /drift?niche=` | Drift report |

## Opportunity score (9 features)

```
score = w_freshness * freshness
      + w_novelty * phrase_novelty
      + w_trend  * trend_momentum
      + w_gap    * supply_demand_gap
      + w_hook   * hookability
      + w_comp   * competitor_gap
      + w_burst  * burst_score
      + w_season * seasonality
      + w_phrase * phrase_novelty
```

Weights come from `system_config.opportunity_weights` (JSON) or, once
trained, from the per-niche GBM’s feature importances.

## Tables touched

`competitor_channels`, `competitor_videos`, `trend_signals`,
`topic_embeddings` (vector(384), IVFFlat index), `research_features`,
`performance_outcomes`, `ml_models`, `bandit_state`, `phrase_bank`.

## Cost

Zero recurring API spend: SBERT runs locally on CPU; trend collection uses
free endpoints; YouTube Data API is within free quota at < 200 channels.

## Related pages

- [[Workflow-NichePulseRefresh]] · [[ML-GBM-Models]] · [[DB-Schema]]
- Long-form: `docs/RESEARCH-INTELLIGENCE.md`
