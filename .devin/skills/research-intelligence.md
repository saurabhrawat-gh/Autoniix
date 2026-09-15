# Skill: Research Intelligence

**Use when:** Working with the research service (`src/services/research/`) or its intelligence modules (trend collector, competitor insights, similarity, opportunity scorer, burst detector, self-learning).

**When NOT to use:** General data analysis or search API work unrelated to this codebase's research pipeline.

---

## Module Map

| Module                 | Purpose                                         | Key Functions                                                                |
| ---------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------- |
| trend_collector.py     | Google Trends + YouTube autocomplete + trending | pytrends, Redis-cached                                                       |
| competitor_insights.py | YouTube Data API competitor analysis            | outlier detection (3-10x avg views), view velocity                           |
| similarity.py          | Dedup + freshness scoring                       | SBERT embeddings (384-dim), SimHash (64-bit), pgvector cosine                |
| opportunity_scorer.py  | 9-feature weighted scoring                      | freshness, novelty, trend_momentum, supply_demand_gap, hookability           |
| burst_detector.py      | Trend burst detection                           | rolling z-score, n-gram phrase mining, seasonality engine (50+ events)       |
| self_learning.py       | ML loop                                         | GBM predictor, Thompson Sampling bandits, feedback, trainer, drift detection |

## Pipeline Flow

```
/research endpoint:
  1. trend_collector.collect()        → trend_signals
  2. competitor_insights.analyze()    → competitor_channels, competitor_videos
  3. similarity.check()               → topic_embeddings, dedup results
  4. burst_detector.detect()          → phrase_bank, burst signals
  5. opportunity_scorer.score()       → research_features, opportunity scores
  6. self_learning.select_bandits()   → bandit selections
  7. Return {topic, research_data, opportunity_score, ...}
```

## Self-Learning Endpoints

- `/feedback` — Ingest YouTube Analytics outcome data
- `/train` — Retrain GBM + update bandit priors
- `/drift` — Check for concept drift
- `/similarity` — Check topic dedup
- `/trends` — Get current trend signals
- `/competitors` — Get competitor data
- `/bursts` — Get burst detection results
- `/phrases` — Get phrase bank

## DB Tables

- `competitor_channels`, `competitor_videos` — YouTube Data API results
- `trend_signals` — Google Trends + autocomplete data
- `topic_embeddings` — SBERT 384-dim vectors with pgvector IVFFlat index
- `research_features` — 9-feature opportunity scores
- `performance_outcomes` — Real-world YouTube Analytics outcomes
- `ml_models`, `bandit_state` — ML model artifacts + bandit arms
- `phrase_bank` — N-gram phrases with novelty scores

## Key Dependencies

- pytrends — Google Trends API
- sentence-transformers (all-MiniLM-L6-v2) — SBERT embeddings, local CPU
- scikit-learn — GBM, calibration
- pgvector — PostgreSQL vector similarity search

## Cost

All intelligence computation is **local**. $0.00 additional API cost.
YouTube Data API has free quota (10,000 units/day).
