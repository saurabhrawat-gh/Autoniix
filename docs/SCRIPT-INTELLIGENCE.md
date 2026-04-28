# Script Intelligence Engine

> Self-learning script generation system that produces 3 synchronized views, learns from YouTube performance data, and minimizes LLM costs through local NLP/ML.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    /generate-script                          │
│                                                              │
│  LLM Phase (Steps 1-4)          Intelligence Phase (5-13)   │
│  ┌─────────────────────┐       ┌──────────────────────────┐ │
│  │ Claude: Generate     │       │ 5. Bandit Selection      │ │
│  │ GPT-4o: Critique     │       │ 6. Humanizer             │ │
│  │ Claude: Rewrite ×3   │       │ 7. NLP Analysis (spaCy)  │ │
│  │ GPT-4o: Re-critique  │       │ 8. Retention Scoring     │ │
│  └─────────────────────┘       │ 9. v1 Voice (Prosody)    │ │
│                                 │ 10. v2 Assets (NER)      │ │
│  💰 LLM cost: ~$0.02-0.06     │ 11. v3 Direction (Rules)  │ │
│                                 │ 12. Features + Predict   │ │
│                                 │ 13. Multi-View QC        │ │
│                                 └──────────────────────────┘ │
│                                  💰 Intelligence cost: $0.00 │
└─────────────────────────────────────────────────────────────┘
```

## 6 Engine Modules

### 1. `script_analyzer.py` — Core NLP Engine
**Foundation for all other engines.** Uses spaCy (`en_core_web_sm`) for:
- Tokenization, POS tagging, NER, dependency parsing
- 500+ word emotion lexicon across 8 categories (curiosity, surprise, fear, hope, urgency, satisfaction, anger, empathy)
- Emphasis word detection (TF-IDF surprise + POS rules + power words)
- Syllable counting & WPM estimation
- Readability scoring (Flesch-Kincaid, Gunning Fog, Dale-Chall via textstat)
- AI pattern detection (20+ robotic phrases)
- Specificity scoring (numbers, names, concrete vs abstract)
- Full segment and script-level analysis

### 2. `retention_optimizer.py` — Attention Economics
Scores scripts on YouTube-specific retention mechanics:
- **Curiosity loops**: opened vs closed, placement quality, density scoring
- **But/Therefore ratio**: South Park causal technique vs sequential "and then"
- **Pattern interrupt frequency**: target one every 20-40 words (~8-15s)
- **Emotional arc**: peaks/valleys, direction changes, climax position
- **Hook strength**: first 5-second deep analysis (curiosity trigger, specificity, emotion, question, power words, word economy)
- **Information density**: unique concepts per 100 words (target 25-45)
- **Specificity score**: concrete numbers/names vs vague abstractions
- **Question engagement**: rhetorical question density

Outputs composite score (0-1) with per-dimension breakdown and actionable recommendations.

### 3. `humanizer.py` — Anti-AI Filter
Transforms AI-generated scripts to sound natural:
- **Contraction injection**: 40+ formal→contraction mappings
- **AI pattern removal**: 17 patterns with natural alternatives
- **Sentence length variation**: breaks monotone rhythm
- **Spoken rhythm enforcement**: em-dashes, breath-point breaks
- **Channel voice adaptation**: slow_philosophical, fast_energetic, gentle_progressive
- Outputs composite humanization score + per-metric breakdown

### 4. `prosody_engine.py` — Script v1 (Voice Over)
Generates voice-optimized version with:
- Per-sentence emotion detection and TTS parameter mapping
- SSML 1.1 markup (emphasis, prosody, breaks, marks)
- Section-based prosody defaults (hook=fast/intense, body=measured, climax=slow/powerful)
- Emotion→TTS parameter map (stability, similarity_boost, style, speed)
- Intelligent pause insertion (punctuation, emotion transitions, section breaks)
- Alignment marks for A/V sync
- Coverage QC (% of sentences with complete prosody data)

### 5. `asset_engine.py` — Script v2 (Asset Generation)
Generates optimized stock footage search queries:
- NER-based primary query generation (people, places, organizations)
- Noun phrase + action verb extraction for specificity
- WordNet synonym expansion for alternate queries
- Emotion→visual mood mapping (lighting, color tone, atmosphere)
- Shot type inference from section/entity context
- Negative keyword generation (avoid stock clichés)
- Animation recipe support (stock_footage, kinetic_text, 2D, 3D)
- Query quality scoring (0-1)
- Coverage QC (% of segments with viable queries)

### 6. `direction_engine.py` — Script v3 (Direction / Editing Config)
Generates frame-accurate Remotion v3 render config:
- Scene preset selection with variety enforcement
- Camera movement templates (push_in, ken_burns, pan, zoom, static)
- Text overlay timing (35ms × character count, capped 1.2-5.0s)
- 3 emphasis effects per segment (scale, color_flash, glow, underline, shake)
- Motion design templates indexed by emotion (particles, floating shapes, pulse rings)
- SFX library (impact, rise, whoosh, shimmer, drop) with trigger timing
- Music shift cues (build, louder, quieter)
- Transition selection with consecutive-same enforcement
- Background strategy from channel colors
- Full render config (fps, resolution, codec, total frames)

## Self-Learning System (`self_learning.py`)

### Feature Extraction
15 script features computed from NLP + retention + humanizer analysis:
```
segment_count, word_count, avg_sentence_length, sentence_length_variance,
hook_strength, curiosity_loop_count, open_loop_ratio, pattern_interrupt_freq,
but_therefore_ratio, contraction_rate, question_density, specificity_score,
readability_score, emotion_variance, emphasis_density
```

### GBM Predictor
- **Model**: GradientBoostingClassifier + isotonic calibration (scikit-learn)
- **Input**: 15 script features
- **Output**: P(success) — probability the script will perform well on YouTube
- **Fallback**: Weighted rule-based scoring when no model trained yet
- **Storage**: Serialized to `script_models` table (model_blob BYTEA)

### Thompson Sampling Bandits
Two bandits for exploration/exploitation:
- **Hook Style Bandit**: 7 arms (shocking_stat, open_loop, pattern_interrupt, story_hook, authority_challenge, contrarian, outcome_promise)
- **Pacing Strategy Bandit**: 5 arms (slow_build, fast_punchy, wave_rhythm, escalating, conversational)
- Beta priors per niche, updated on each outcome

### Feedback Loop
```
generate_script → store_features → [YouTube publishes] → analytics 48h
→ ingest_performance → label (success/weak/average/strong/viral)
→ update_bandits → [weekly] retrain_model → drift_detection
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `script_features` | 15+ feature vectors per script |
| `script_outcomes` | YouTube metrics + success labels |
| `script_models` | Trained GBM/regressor blobs |
| `script_bandit_state` | Thompson Sampling Beta priors |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/generate-script` | POST | Full pipeline: LLM + Intelligence → 3 views |
| `/script-feedback` | POST | Ingest YouTube analytics for learning |
| `/script-train` | POST | Train/retrain success predictor |
| `/script-drift` | GET | Check model degradation |
| `/generate-hooks` | POST | Hook generation (existing) |
| `/package` | POST | Metadata packaging (existing) |

## Response Structure

`/generate-script` returns:
```json
{
  "status": "success",
  "data": {
    "script_base": { "segments": [...], "critique": {...}, "retention_score": {...} },
    "script_voice": { "segments": [...], "full_ssml": "...", "emotion_curve": [...] },
    "script_assets": { "segments": [...], "qc": {...} },
    "script_direction": { "render_config": {...}, "segments": [...], "qc": {...} },
    "bandit_selections": { "hook_style": "...", "pacing_strategy": "..." },
    "intelligence_scores": { "humanization": 0.8, "retention": 0.7, ... }
  },
  "cost": { "cost_usd": 0.05, "provider": "multi" }
}
```

## Dependencies

All local, zero additional API cost:
- `spacy` (en_core_web_sm) — NLP pipeline
- `textstat` — readability metrics
- `nltk` (WordNet) — synonym expansion
- `scikit-learn` — GBM + calibration
- `numpy` — numerical operations

## Configuration (`system_config`)

| Key | Default | Description |
|-----|---------|-------------|
| `script_min_retention_score` | 0.60 | Min retention composite |
| `script_min_humanization_score` | 0.65 | Min humanizer composite |
| `script_min_prosody_coverage` | 0.90 | Min prosody coverage ratio |
| `script_min_asset_coverage` | 0.85 | Min asset query coverage |
| `script_max_ai_pattern_density` | 0.02 | Max AI pattern density |
| `script_target_wpm_short` | 160 | Target WPM short-form |
| `script_target_wpm_long` | 145 | Target WPM long-form |
| `script_ml_retrain_min_samples` | 15 | Min samples for retrain |
| `script_bandit_exploration` | 0.15 | Exploration weight |
| `script_feature_weights` | JSON | Default feature weights |
| `script_hook_styles` | JSON | Bandit hook arms |
| `script_pacing_strategies` | JSON | Bandit pacing arms |
