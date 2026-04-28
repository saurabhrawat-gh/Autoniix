# Research Intelligence — Upgraded Research Service

## Overview

The research service has been upgraded from a basic multi-source search + LLM synthesis pipeline to a **self-learning, data-driven research intelligence engine**. The upgrade adds 6 new modules, 8 new DB tables, and 8 new API endpoints — all with **zero additional API cost**.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    /research endpoint                         │
├──────────────────────────────────────────────────────────────┤
│  Step 1: Multi-Source Search (YouTube, Google, Reddit, News) │
│  Step 2: LLM Research Synthesis + Quality Gate               │
│  Step 3: Fact-Check Claims                                   │
│  Step 4: Intelligence Layer (NEW — zero API cost)            │
│    ├─ 4a. Trend Collector (Google Trends + YT Suggestions)   │
│    ├─ 4b. Competitor Insights (outlier detection)            │
│    ├─ 4c. Burst Detection (rolling z-scores)                 │
│    ├─ 4d. Phrase Mining (rising keyphrases)                   │
│    ├─ 4e. Similarity Check (SBERT + SimHash + pgvector)      │
│    ├─ 4f. Freshness Score                                    │
│    ├─ 4g. Phrase Novelty                                     │
│    ├─ 4h. Seasonality Engine                                 │
│    ├─ 4i. Opportunity Score (weighted multi-signal)           │
│    ├─ 4j. ML Prediction (GBM success predictor)              │
│    ├─ 4k. Thompson Sampling (explore vs exploit)             │
│    ├─ 4l. Store Embedding (for future dedup)                 │
│    └─ 4m. Store Features (for ML training)                   │
└──────────────────────────────────────────────────────────────┘
```

## New Modules

### 1. Trend Collector (`trend_collector.py`)
- **Google Trends** via pytrends: momentum scores, rising/related queries, topic suggestions
- **YouTube autocomplete** suggestions (free, no API key)
- **YouTube trending videos** in niche (uses existing YouTube Data API quota)
- 6-hour Redis caching to minimize API calls
- Stores snapshots in `trend_signals` table

### 2. Competitor Insights (`competitor_insights.py`)
- Discovers or tracks named competitor channels
- Fetches recent videos + statistics in batch
- **Outlier detection**: flags videos that outperform their channel's average by 3-10x
- **View velocity**: estimates views/24h based on age
- **Niche-wide outlier search**: finds small channels with viral hits
- Stores data in `competitor_channels` + `competitor_videos`

### 3. Similarity & Freshness (`similarity.py`)
- **SBERT embeddings** (all-MiniLM-L6-v2, 384-dim) — runs locally, zero cost
- **SimHash** (64-bit locality-sensitive hash) for fast near-duplicate screening
- **pgvector** cosine similarity search for semantic deduplication
- **Freshness score**: weighted combination of our recency, trend momentum, competitor coverage
- Prevents topic repetition across channels

### 4. Opportunity Scorer (`opportunity_scorer.py`)
- **9-feature weighted scoring**: freshness, novelty, trend momentum, supply-demand gap, hookability, competitor gap, burst score, seasonality, phrase novelty
- **Hookability heuristics**: curiosity gap, numbers, controversy, emotional words, power words, question format
- **Supply-demand gap**: high trend volume + low competitor supply = high opportunity
- Weights configurable via `system_config` or learned from ML model

### 5. Self-Learning Model (`self_learning.py`)
- **GBM predictor**: Gradient Boosted classifier predicting P(success) from research features
- **Thompson Sampling bandit**: explores new topic clusters while exploiting known winners
- **Feedback ingestor**: pulls YouTube Analytics (views, CTR, AVD%, engagement) and labels success/failure
- **Trainer**: cross-validated training with isotonic calibration; auto-derives new opportunity weights from feature importances
- **Drift detection**: monitors recent AUC and triggers retrain alerts

### 6. Burst Detector + Phrase Miner + Seasonality (`burst_detector.py`)
- **Burst detection**: rolling z-scores on trend signal time-series; z > 2.0 = burst
- **Phrase mining**: n-gram extraction from competitor titles, growth rate analysis, rising phrase identification
- **Phrase novelty**: scores how much a topic uses fresh, rising language
- **Seasonality engine**: 50+ seasonal events across 12 months, historical performance correlation

## New Database Tables

| Table | Purpose |
|-------|---------|
| `competitor_channels` | Tracked competitor channels per niche |
| `competitor_videos` | Competitor video stats, outlier flags, view velocity |
| `trend_signals` | Google Trends momentum snapshots, burst flags |
| `topic_embeddings` | SBERT 384-dim embeddings + SimHash for dedup (pgvector) |
| `research_features` | 9-feature vectors for every researched topic (ML training data) |
| `performance_outcomes` | YouTube analytics labels (views, CTR, AVD, engagement, success tier) |
| `ml_models` | Serialized trained models + metrics + versioning |
| `bandit_state` | Thompson Sampling Beta(α,β) priors per niche/arm |
| `phrase_bank` | Rising/saturated phrases per niche |

## New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/feedback` | POST | Ingest YouTube analytics for self-learning |
| `/train` | POST | Train/retrain the success predictor model |
| `/drift` | GET | Check if ML model needs retraining |
| `/similarity` | POST | Check topic against existing catalog |
| `/trends` | POST | Collect trend signals for a niche |
| `/competitors` | POST | Analyze competitors, find outliers |
| `/bursts` | GET | Detect bursting keywords |
| `/phrases` | GET | Get rising phrases for a niche |

## New Config Thresholds (seed-data.sql)

| Key | Default | Description |
|-----|---------|-------------|
| `opportunity_score_min` | 0.45 | Min opportunity score for topic selection |
| `novelty_score_min` | 0.30 | Min novelty (below = too similar) |
| `freshness_score_min` | 0.25 | Min freshness score |
| `duplicate_similarity_max` | 0.35 | Max cosine sim before flagging duplicate |
| `burst_z_threshold` | 2.0 | Z-score for burst detection |
| `ml_retrain_min_samples` | 20 | Min labeled samples to train ML model |
| `opportunity_weights` | JSON | Configurable feature weights |

## Self-Learning Feedback Loop

```
Video Published → YouTube Analytics (48h) → /feedback endpoint
         ↓
    performance_outcomes (labels: success/failure + tier)
         ↓
    Bandit Update (reward for selected arm)
         ↓
    Weekly /train → GBM retrained on research_features × performance_outcomes
         ↓
    Updated model → opportunity_weights adjusted by feature importances
         ↓
    Next /research call uses new model + new weights
```

## Benefits

### 1. Zero Additional Cost
All new modules run locally:
- **SBERT** embeddings: CPU-only, ~80MB model
- **scikit-learn** GBM: trains in seconds
- **pytrends**: free Google Trends API
- **YouTube autocomplete**: free, no API key
- **SimHash/burst/phrase mining**: pure Python math

### 2. Automatic Topic Deduplication
- No more accidentally covering the same topic twice
- Cross-channel similarity detection prevents "echo chamber"
- SimHash catches near-duplicates in O(1)

### 3. Data-Driven Topic Selection
- Replaces gut-feeling with **9-dimensional opportunity scoring**
- Each dimension is measurable and tunable
- Weights evolve automatically as performance data accumulates

### 4. Competitive Intelligence
- Knows what competitors are publishing and what's working
- **Outlier detection** surfaces "blue ocean" topics — small channels hitting big
- Supply-demand gap analysis prevents entering saturated topic spaces

### 5. Trend-Riding
- **Google Trends momentum** catches rising topics before they peak
- **Burst detection** identifies sudden spikes worth covering NOW
- **YouTube suggestions** reveal what audiences are actively searching

### 6. Self-Improving Over Time
- Every video published becomes training data
- GBM model learns which feature combinations predict success
- Thompson Sampling naturally balances exploring new angles vs doubling down on winners
- Weekly retrain + drift detection prevents model staleness

### 7. Seasonal Awareness
- 50+ calendar events mapped across 12 months
- Historical performance correlation (learns which months work best per niche)
- 1-month planning horizon catches upcoming events early

### 8. Rising Language Detection
- Phrase mining identifies the language audiences are adopting
- Topics using rising phrases score higher
- Saturated phrases are penalized

## Infrastructure Changes

- **postgres-app**: upgraded to `pgvector/pgvector:pg15` image
- **research service**: memory increased to 1.5GB (for SBERT model)
- **requirements.txt**: added `pytrends`, `sentence-transformers`, `scikit-learn`, `numpy`
- **init-db.sql**: `CREATE EXTENSION vector` + 8 new tables + pgvector indexes
