# Service: Editor

## Purpose

The post-production stage between assembly and render. Optimises the
timeline, generates captions from voice word-timestamps, and runs a final
QC pass that can demand a re-edit.

## Port / source

- Port `8013`, memory 512M
- `src/services/editor/main.py`
- Modules:
  - `timeline_optimizer.py` — trims dead air, beat-aligns cuts to music
  - `caption_generator.py` — SRT + styled overlays from word timestamps
  - `final_qc.py` — last-line defence: clipping, audio peaks, freeze frames,
    text-overflow, brand-safety re-check

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /post-produce` | Timeline + captions + QC |
| `POST /captions` | Captions only |
| `POST /final-qc` | QC only |

## Related pages

- [[Service-Assembly]] · [[Quality-Gates]] · [[Service-Voice]]
