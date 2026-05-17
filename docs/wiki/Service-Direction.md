# Service: Direction

## Purpose

Produces the rich per-segment direction v3 (camera, text strategy, motion
design, audio cues, background strategy) that the Remotion compositions
consume. Acts as creative-to-technical translator between the script’s
intent and the renderer’s primitives.

## Port / source

- Port `8010`, memory 512M
- `src/services/direction/main.py`
- `direction_merger.py` — merges Script v3 direction with channel brand
  templates and the asset resolver output

## Output schema (per segment)

```json
{
  "camera":         {"move": "slow_push_in", "start": [...], "end": [...]},
  "text_strategy":  {"type": "kinetic_headline", "emphasis_words": [...] },
  "motion_design":  {"recipe": "reveal_zoom", "intensity": 0.6 },
  "audio_cues":     [{"sfx": "whoosh", "at": 0.4 }],
  "background":     {"strategy": "depth_blur", "color": "#0e0e0e" },
  "transition":     {"to_next": "hard_cut" }
}
```

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /direct` | Build full direction script |
| `POST /score-direction` | QC scorer (transition variety, audio coverage) |
| `POST /direction-feedback` |  Outcome ingest |

## Quality target

`direction_score >= 8.5` enforced by [[Quality-Gates]].

## Related pages

- [[Service-Script]] · [[Service-Assembly]] · [[Service-Remotion]]
