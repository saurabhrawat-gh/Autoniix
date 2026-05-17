# Service: Script

## Purpose

Generates the script in four representations — base voiceover script, voice
script (SSML + prosody), asset script (per-segment NER queries + animation
recipes) and direction script (camera/text/motion/SFX). Runs a 13-step
pipeline that mixes LLM calls with local NLP intelligence.

## Port / source

- Port `8002`, memory 1536M
- `src/services/script/main.py:1-1000`
- Modules:
  - `script_analyzer.py` — spaCy + textstat + 500+ word emotion lexicon
  - `retention_optimizer.py` — curiosity loops, But/Therefore ratio,
    pattern-interrupt frequency, emotional arc
  - `humanizer.py` — 17 AI-pattern replacements, 40+ contraction mappings,
    sentence-variation, rhythm
  - `prosody_engine.py` — per-sentence SSML, emotion→TTS params, pauses,
    alignment marks
  - `asset_engine.py` — NER + WordNet synonyms + emotion→mood map
  - `direction_engine.py` — scene presets, camera templates, animation
    recipes for stock / kinetic_text / 2D / 3D
  - `self_learning.py` — GBM + Thompson Sampling (hook style, pacing)

## Pipeline (13 steps)

1–4. LLM: research synthesis → outline → base draft → critique-and-rewrite
   (up to 3 rewrites, target composite ≥ 9.0).
5. `script_analyzer` features.
6. `retention_optimizer` scores + suggestions.
7. `humanizer` pass.
8. `prosody_engine` → `script_voice`.
9. `asset_engine` → `script_assets`.
10. `direction_engine` → `script_direction`.
11. Hook/pacing bandit selection.
12. Self-learning prediction (`script_gbm`) for retention.
13. Persist features + bandit selections to `script_features`.

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /generate-script` | Full 13-step pipeline. Returns `{script_base, script_voice, script_assets, script_direction, bandit_selections, intelligence_scores}` |
| `POST /script-feedback` | Outcome ingest |
| `POST /script-train` | Retrain niche GBM |
| `GET  /script-drift` | Drift report |

## Quality target

Composite ≥ 9.0 on the 8 critique dimensions (specificity, structure, hook,
clarity, emphasis, pacing, scene-direction quality, retention-curve).

## Tables

`script_features`, `script_outcomes`, `script_models`, `script_bandit_state`.

## Related pages

- [[Workflow-VideoProduction]]
- [[Quality-Gates]]
- Long-form: `docs/SCRIPT-INTELLIGENCE.md`
