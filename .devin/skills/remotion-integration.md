# Skill: Remotion Integration

**Use when:** Working with the assembly→render pipeline, Remotion v3 render config, direction JSON schema, asset mapping, or the yt-automation-remotion repo.

**When NOT to use:** General TypeScript/React work unrelated to video rendering.

---

## Architecture

```
Assembly Service (Python)  →  Remotion API (Express)  →  Remotion Worker (BullMQ + Chromium)
     src/services/assembly/      yt-automation-remotion/       yt-automation-remotion/
     port 5006                   port 4000                     headless Chrome
```

- Assembly generates **direction v3 JSON** — the complete render specification.
- Remotion API receives the JSON, enqueues a render job via BullMQ (shared Redis).
- Remotion Worker picks up the job, renders via Chromium, uploads to MinIO (shared storage).

## Direction v3 JSON Schema

Each segment in the direction JSON includes:

```json
{
  "camera": { "shot_type": "medium", "movement": "slow_zoom_in" },
  "text_strategy": { "animation": "fade_up", "position": "center_bottom" },
  "motion_design": { "type": "ken_burns", "intensity": 0.3 },
  "audio_cues": { "sfx": "whoosh", "volume": 0.5 },
  "background_strategy": { "type": "stock", "mood": "warm" }
}
```

## Asset Mapping

- Stock footage: Pixabay + Pexels + Envato Elements (parallel search)
- Music/SFX: Freesound + Pixabay
- Thumbnails: DALL-E
- All assets stored in MinIO with content-prefixed keys: `test/` or `prod/`

## Render Flow

1. Assembly calls `POST http://remotion-api:4000/render` with direction JSON
2. Remotion API enqueues job in BullMQ (Redis queue `remotion-render`)
3. Worker renders video, uploads to MinIO
4. Assembly polls for completion or receives callback

## Test vs Production

- Test mode: 640x360 @ 15fps (fast, low quality)
- Production mode: 1920x1080 @ 30fps (full quality)

## Key Files

- `src/services/assembly/main.py` — Pre-render sync validation, direction v3 generation
- `src/services/direction/direction_merger.py` — Merges direction from multiple sources
- `src/services/script/direction_engine.py` — Generates direction v3 from script
- `yt-automation-remotion/` — Separate repo, TypeScript/React/Remotion v3

## REMOTION_BASE_URL

`http://remotion-api:4000` (Docker) or `http://localhost:4000` (local dev)
