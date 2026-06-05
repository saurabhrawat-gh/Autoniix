# Skill: Script Intelligence

**Use when:** Working with the script service (`src/services/script/`) or its intelligence modules (analyzer, retention, humanizer, prosody, asset engine, direction engine, self-learning).

**When NOT to use:** General NLP/ML work unrelated to this codebase's script pipeline.

---

## Module Map

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| script_analyzer.py | Core NLP analysis | emotion detection, emphasis scoring, readability, AI pattern detection, specificity |
| retention_optimizer.py | Attention economics | curiosity loops, But/Therefore ratio, pattern interrupt, emotional arc, hook strength |
| humanizer.py | Anti-AI filter | 40+ contractions, 17 AI pattern replacements, sentence variation, spoken rhythm |
| prosody_engine.py | Script v1 Voice | per-sentence SSML, emotion→TTS mapping, section prosody, pause rules |
| asset_engine.py | Script v2 Assets | NER-based queries, WordNet synonyms, emotion→visual mood, shot type inference |
| direction_engine.py | Script v3 Direction | scene presets, camera templates, motion design, SFX library, Remotion v3 config |
| self_learning.py | ML loop | GBM predictor, Thompson Sampling bandits, feedback ingestor, drift detection |

## Pipeline Flow

```
/generate-script endpoint:
  LLM Steps 1-4:   ideation → script_v1 → critique → rewrite
  Intelligence 5-13:
    5. script_analyzer.analyze()           → script_features
    6. retention_optimizer.optimize()       → retention_scores
    7. humanizer.humanize()                → humanized_script
    8. prosody_engine.generate_prosody()   → script_voice (SSML)
    9. asset_engine.generate_assets()      → script_assets (queries, moods)
    10. direction_engine.generate()        → script_direction (Remotion v3)
    11. self_learning.select_bandits()     → bandit_selections
    12. self_learning.compute_scores()     → intelligence_scores
    13. Return {script_base, script_voice, script_assets, script_direction, ...}
```

## Self-Learning Endpoints
- `/script-feedback` — Ingest outcome data (retention, engagement)
- `/script-train` — Retrain GBM + update bandit priors
- `/script-drift` — Check for concept drift in predictions

## DB Tables
- `script_features` — Per-script NLP features (emotion, readability, specificity, etc.)
- `script_outcomes` — Real-world outcomes (retention, engagement, CTR)
- `script_models` — Trained GBM model artifacts
- `script_bandit_state` — Thompson Sampling arm states (hook_style, pacing_strategy)

## Dependencies
- spaCy (en_core_web_sm) — NLP, NER, POS
- textstat — readability metrics
- NLTK WordNet — synonym expansion
- scikit-learn — GBM, calibration
- numpy — numerical operations

## Cost
All intelligence computation is **local**. $0.00 additional API cost per script.
