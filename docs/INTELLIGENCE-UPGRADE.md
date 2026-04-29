# Intelligence Layer Upgrade

## Overview

This document describes the intelligence layer added to every service in the yt-automation pipeline. The primary goals are:

1. **Reduce LLM costs** by replacing API calls with local AI/ML models where possible
2. **Improve quality** through self-learning feedback loops
3. **Add new capabilities** via Brand Identity and Editor/Post-Production services

All intelligence computation runs locally (CPU). Zero additional API cost except when LLM fallbacks are triggered.

---

## Architecture Summary

```
Research → Brand Identity → Script → Voice → Assets + Thumbnail + Music → Direction → Editor → Assembly → Delivery → Analytics
   │            │             │        │         │          │                  │           │          │          │          │
   └─ ML ──────└─ Local ─────└─ NLP ──└─ ML ───└─ ML ────└─ ML ─────────────└─ Local ──└─ Local ──└─ Local ──└─ Local ──└─ ML
```

### New Services

| Service | Port | Intelligence Module | Purpose |
|---------|------|---------------------|---------|
| **Brand Identity** | 8012 | `brand_dna.py` | Brand fingerprinting, style consistency scoring |
| **Editor** | 8013 | `timeline_optimizer.py`, `caption_generator.py`, `final_qc.py` | Post-production pacing, captions, pre-render QC |

### Upgraded Services

| Service | Port | Intelligence Modules | Key Capability |
|---------|------|---------------------|----------------|
| **Voice** | 8003 | `emotion_predictor.py`, `audio_quality_scorer.py`, `voice_style_learner.py` | Local emotion mapping (skips LLM), audio quality analysis, self-learning TTS params |
| **Assets** | 8004 | `query_optimizer.py` | Query expansion, asset caching, relevance scoring |
| **Thumbnail** | 8005 | `composition_analyzer.py`, `ctr_predictor.py` | Local composition QC (skips Vision API), ML CTR prediction |
| **Direction** | 8010 | `direction_merger.py` | Script v3 hint merging (skips LLM when hints are sufficient) |
| **Assembly** | 8006 | `render_predictor.py` | Complexity analysis, render duration estimation, smart retry with simplified direction |
| **Delivery** | 8007 | `seo_optimizer.py` | Title/description/tag SEO scoring, optimal upload time |
| **Analytics** | 8008 | `pattern_miner.py` | Performance pattern mining, content fatigue detection |

---

## LLM Cost Reduction Strategy

Each service follows a **local-first, LLM-fallback** pattern:

### Voice Service
- **Before**: LLM call to map emotions for every sentence ($0.003-0.01/video)
- **After**: Local keyword-based emotion predictor handles 80%+ of cases. LLM only used when prosody hints are absent.
- **Savings**: ~$0.005/video

### Thumbnail Service
- **Before**: GPT-4 Vision QC for every variant ($0.01-0.03/video)
- **After**: Local OpenCV composition analysis runs first. Vision QC skipped when local score ≥ 8.5 (configurable via `thumb_local_qc_skip_threshold`).
- **Savings**: ~$0.015/video per skipped Vision call

### Direction Service
- **Before**: GPT-4 generates full direction for every video ($0.01-0.02/video)
- **After**: Script v3 direction hints are merged with actual assets locally. LLM skipped when merged score ≥ 7.0 (configurable via `direction_use_script_v3_hint`).
- **Savings**: ~$0.015/video

### Estimated Total Savings
- **Per video**: $0.03-0.05
- **At 100 channels × 30 videos/month**: $90-150/month

---

## Self-Learning Systems

### Voice Style Learner (`voice_style_learner.py`)
- **Model**: Gradient Boosted Machine (sklearn)
- **Features**: Audio metrics (SNR, RMS, spectral), sentence count, emotion distribution
- **Target**: Optimal TTS parameters (stability, similarity_boost, style, speed)
- **Training**: Triggered via `/voice-train` endpoint with retention data
- **Feedback**: `/voice-feedback` ingests retention metrics

### Thumbnail CTR Predictor (`ctr_predictor.py`)
- **Model**: GBM Regressor (sklearn)
- **Features**: Composition metrics (face count, brightness, saturation, contrast, rule-of-thirds adherence)
- **Target**: Click-through rate
- **Training**: `/thumbnail-train` with historical CTR data
- **Feedback**: `/thumbnail-feedback` ingests actual CTR + impressions

### Analytics Pattern Miner (`pattern_miner.py`)
- **Discovery**: Score-performance correlations, tier distributions, anomaly detection
- **Mining**: High-performer trait extraction, content fatigue detection
- **Endpoints**: `/mine-patterns`, `/insights/{channel_id}`

---

## New API Endpoints

### Brand Identity Service (port 8012)
- `POST /brand-profile` — Get or create brand profile
- `POST /brand-consistency` — Score content against brand identity
- `GET /brand-evolution/{channel_id}` — Track brand changes over time

### Editor Service (port 8013)
- `POST /post-produce` — Full post-production pipeline (pacing, captions, QC)

### Intelligence Endpoints (added to existing services)
- `POST /voice-feedback` — Ingest voice retention data
- `POST /voice-train` — Train voice optimization model
- `POST /thumbnail-feedback` — Ingest CTR data
- `POST /thumbnail-train` — Train CTR prediction model
- `POST /seo-score` — Score title/description/tags for SEO
- `POST /mine-patterns` — Discover performance patterns
- `GET /insights/{channel_id}` — Get stored channel insights

---

## Database Tables Added

All tables created in `scripts/init-db.sql`:

| Table | Service | Purpose |
|-------|---------|---------|
| `brand_profiles` | Brand | Brand fingerprints per channel |
| `brand_assets` | Brand | Tracked brand assets |
| `brand_style_history` | Brand | Style evolution tracking |
| `voice_features` | Voice | Audio feature vectors for ML |
| `voice_outcomes` | Voice | Retention outcome labels |
| `voice_models` | Voice | Trained GBM model storage |
| `asset_library` | Assets | Cached asset library |
| `asset_search_log` | Assets | Search query logs |
| `thumbnail_features` | Thumbnail | Composition feature vectors |
| `thumbnail_outcomes` | Thumbnail | CTR outcome labels |
| `direction_features` | Direction | Direction complexity features |
| `editor_sessions` | Editor | Post-production session logs |
| `assembly_render_log` | Assembly | Render attempt logs |
| `delivery_features` | Delivery | SEO feature vectors |
| `analytics_patterns` | Analytics | Mined performance patterns |

---

## Configuration Keys

Added to `scripts/seed-data.sql` (system_config table):

| Key | Default | Description |
|-----|---------|-------------|
| `voice_use_prosody_hints` | `true` | Enable local emotion prediction |
| `voice_ml_blend_weight` | `0.3` | ML-learned param influence (0-1) |
| `asset_cache_enabled` | `true` | Enable asset caching |
| `asset_relevance_threshold` | `6.0` | Min relevance score for stock clips |
| `thumb_local_qc_skip_threshold` | `8.5` | Skip Vision QC above this local score |
| `thumb_ctr_model_enabled` | `true` | Enable ML CTR prediction |
| `direction_use_script_v3_hint` | `true` | Enable script hint direction merging |
| `direction_llm_enhance_enabled` | `true` | Always enhance with LLM even if hints exist |
| `editor_pacing_enabled` | `true` | Enable timeline pacing optimization |
| `editor_qc_min_score` | `7.0` | Minimum QC score to proceed |
| `assembly_max_complexity` | `15` | Warn above this complexity score |
| `delivery_seo_min_score` | `6.0` | Minimum SEO score warning threshold |
| `analytics_pattern_min_videos` | `10` | Min videos needed for pattern mining |
| `brand_consistency_threshold` | `0.7` | Min brand consistency score |

---

## Docker Compose Changes

- **New containers**: `brand` (8012), `editor` (8013) — 512M each
- **Memory increases**: voice (512M→768M), thumbnail (512M→768M), assembly (256M→512M), analytics (256M→512M)
- **Total new memory**: ~2.5GB additional
- **Total containers**: 21 (was 19)

---

## Temporal Workflow Changes

`video_production.py` updated pipeline:

1. **Research** — unchanged
2. **Brand Identity** (NEW) — loads/creates brand profile for channel
3. **Script** — unchanged (already has intelligence from previous upgrade)
4. **Voice** — now uses local emotion prediction + ML-learned params
5. **Assets + Thumbnail + Music** (parallel) — assets use cache + relevance scoring; thumbnails use local QC
6. **Direction** — tries script v3 hint merge before LLM
7. **Editor/Post-Production** (NEW) — pacing optimization, caption generation, final QC
8. **Assembly** — complexity analysis + smart retry on failure
9. **Human Review Gate** — unchanged
10. **Delivery** — SEO scoring before upload
11. **Analytics + Brand Consistency** — pattern mining + brand check on final output

---

## Dependencies Added

In `requirements.txt`:
- `Pillow` — Image/thumbnail analysis
- `librosa`, `soundfile` — Audio quality analysis
- `opencv-python-headless` — Face detection, composition analysis
- `pydub` — Audio concatenation
- `scikit-learn` — GBM models for self-learning
- `sentence-transformers` — Embeddings (already present for research)
- `spacy` — NLP pipeline (already present for script)
- `numpy` — Numerical computation (already present)
