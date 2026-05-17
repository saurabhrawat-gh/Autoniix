# Service: Assembly

## Purpose

Pre-render validation and Remotion render-payload assembly. Catches
timeline mismatches, missing assets, and asset/voice misalignment **before**
spending the most expensive resource (render compute).

## Port / source

- Port `8006`, memory 512M
- `src/services/assembly/main.py`
- `render_predictor.py` — GBM that estimates render duration and
  complexity; may **simplify** scenes (drop animations) if predicted
  render > budget

## Validations

| Check | Action on failure |
|---|---|
| Timeline continuity (segments cover full duration, no gaps) | Pad with silence or warn |
| Voice-text alignment (TTS word timestamps map to script tokens) | Re-run voice for offending segment |
| Asset coverage (every segment has an asset) | Escalate to assets service |
| `text_strategy` matches scene type | Auto-fix or escalate |
| Audio master loudness target (–14 LUFS) | Normalise in assembly |

## Render payload

Produces the `RenderConfig` consumed by Remotion. Includes per-scene:
- Source asset URLs (presigned for private, plain for public)
- Voice tracks + word timestamps
- Caption blocks
- Camera moves, text-strategy, motion-design, audio cues from
  `script_direction`
- Background music track (selected by `music_activity` from a curated
  pool by mood/tempo)
- Final QC report passthrough from the editor service

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /assemble` | Validate + build payload + (optionally) submit to Remotion |
| `POST /validate` | Validation only |
| `POST /assembly-feedback` | Outcome ingest |

## Test-mode behaviour

In test mode `assemble` overrides render resolution to **640×360@15fps** so
the full pipeline can run in seconds on CPU-only hardware.

## Related pages

- [[Service-Remotion]]
- [[Service-Editor]]
- [[Quality-Gates]]
