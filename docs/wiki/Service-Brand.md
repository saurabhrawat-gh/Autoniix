# Service: Brand

## Purpose

Enforces per-channel brand DNA — the visual / verbal / tonal identity that
must persist across every video on that channel.

## Port / source

- Port `8012`, memory 512M
- `src/services/brand/main.py`
- `brand_dna.py` — stores per-channel palette, fonts, voice persona, jingle,
  text-overlay grammar, banned topics, brand-safety filters

## Phases it runs in

1. **Pre-script (Phase 1B `brand_check`)** — validates the chosen topic
   against brand-DNA banned topics and tone.
2. **Post-delivery (consistency check)** — scores the delivered video on
   brand fit using the thumbnail Vision QC + audio fingerprint.

## Endpoints

| Method + Path | Purpose |
|---|---|
| `GET  /brand/{channel_id}` | Brand DNA snapshot |
| `PUT  /brand/{channel_id}` | Update DNA |
| `POST /check-topic` | Pre-script approval |
| `POST /check-delivered` | Post-delivery consistency score |

## Related pages

- [[Workflow-VideoProduction]] · [[BFF-Channels]]
