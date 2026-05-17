# Service: Thumbnail

## Purpose

Generates 3 thumbnail variants per video, scores them with GPT-4o Vision
QC, and optionally regenerates (max 2 retries) to clear the
`thumbnail_score >= 9.0` gate.

## Port / source

- Port `8005`, memory 768M
- `src/services/thumbnail/main.py`
- Modules:
  - `composition_analyzer.py` — rule-of-thirds, face placement, contrast
  - `ctr_predictor.py` — GBM trained on competitor thumbnails + observed CTR

## Flow

1. Build 3 prompts (200+ words each) from the video concept: `text_style`,
   `composition_rule`, `emotion_trigger`, channel brand DNA.
2. DALL·E renders 1024×1024 (or vertical for shorts).
3. GPT-4o Vision scores each on 6 dimensions (clarity, emotion, hook,
   composition, brand-fit, text-legibility).
4. `ctr_predictor` predicts click-through and blends with vision score.
5. If best < threshold: regenerate variants with adjusted prompt (max 2x).
6. Winner uploaded to `public/` MinIO prefix so YouTube can fetch it
   directly (no presigning needed).

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /generate-thumbnails` | Full flow, returns top variant + losers |
| `POST /score-thumbnail` | Vision QC only |
| `POST /thumbnail-feedback` | Outcome ingest |
| `POST /thumbnail-train` | Retrain `thumbnail_ctr_gbm` |

## Output payload

```json
{
  "winner": {"url": "https://...", "score": 9.2, "scores": {...}},
  "variants": [...],
  "regen_attempts": 1
}
```

## Related pages

- [[Providers-Image]]
- [[ML-GBM-Models]]
- [[Quality-Gates]]
