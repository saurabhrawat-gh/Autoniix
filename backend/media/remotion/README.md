# yt-automation-remotion

Remotion-based video renderer service for the YT automation pipeline.
Exposes an HTTP API that accepts a **Direction Format v3** JSON and
produces MP4 / WebM / PNG outputs, uploaded to S3/R2 and announced via webhook.

> Phase 0 scaffold. See [`docs/`](./docs) for the full architecture (components, presets, phases).

---

## Quick start (local)

```bash
cp .env.example .env
# Fill in S3_* vars (or any S3-compatible: R2, MinIO)

npm install

# Terminal 1 — Redis
docker run --rm -p 6379:6379 redis:7-alpine

# Terminal 2 — API
npm run api

# Terminal 3 — worker
npm run worker
```

Preview compositions in a UI:

```bash
npm run studio
```

Smoke test (renders a 5-sec black video, uploads if S3 configured):

```bash
npm run smoke
```

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

This starts `redis`, `api` (port 4000), and `worker`.

---

## API

| Method | Path              | Purpose                        |
| ------ | ----------------- | ------------------------------ |
| `POST` | `/api/render`     | Enqueue a video render         |
| `POST` | `/api/thumbnail`  | Enqueue a thumbnail render     |
| `GET`  | `/api/render/:id` | Status + progress + output URL |
| `GET`  | `/api/health`     | Queue counts, memory           |

### Example

```bash
curl -X POST http://localhost:4000/api/render \
  -H 'content-type: application/json' \
  -d '{
    "composition": "MainVideo",
    "codec": "h264",
    "outputFormat": "mp4",
    "callbackUrl": "https://n8n.example/webhook/remotion-render-complete",
    "inputProps": {
      "direction": {
        "version": "3.0",
        "meta": { "video_id":"v1","channel_id":"c1","title":"Test",
          "duration_target_seconds":5,"aspect":"16:9","fps":30,
          "resolution":{"width":1920,"height":1080} },
        "template": "hybrid-kinetic",
        "theme": { "primary_color":"#FF3B30","accent_color":"#FFD60A",
          "background_color":"#000","text_color":"#FFF",
          "fonts":{"heading":"Inter","body":"Inter"} },
        "grade_preset": "fx.grade.cinematic_teal_orange",
        "segments": [
          { "id":"s1","start_ms":0,"duration_ms":5000,
            "scene_preset":"scene.placeholder",
            "scene_overrides":{"label":"Hello"} }
        ]
      }
    }
  }'
```

Response:

```json
{ "renderId": "render_abc123", "status": "rendering", "estimatedDuration": 180 }
```

Poll:

```bash
curl http://localhost:4000/api/render/render_abc123
```

When complete, the worker POSTs to `callbackUrl`:

```json
{
  "renderId": "render_abc123",
  "status": "done",
  "outputUrl": "https://.../render_abc123.mp4",
  "fileSize": 5242880,
  "duration": 12
}
```

---

## Project layout

```
src/
├── Root.tsx                    # Remotion root — registers all compositions
├── index.ts                    # Remotion entry point
├── compositions/               # MainVideo (16:9), ShortFormVideo (9:16), ThumbnailComp
├── components/
│   └── scenes/                 # SceneRenderer + PlaceholderScene (Phase 0)
├── registry/                   # Preset registry: scenes, transitions, animations, effects, overlays
├── schemas/                    # directionV3.ts — Zod schema for the JSON contract
├── utils/                      # env, logger, storage (S3), callback (webhook)
├── api/                        # Express server + BullMQ queue
└── worker/                     # BullMQ worker → renderer.ts (bundle + render + upload)

scripts/smoke.ts                # Phase 0 deliverable check
docs/                           # Architecture, build plan, registry pattern, schema
Dockerfile, docker-compose.yml  # App + redis
.github/workflows/ci.yml        # typecheck + lint
```

---

## The Preset pattern (how we scale to 100s of "effects")

See [`docs/C-preset-registry-pattern.md`](./docs/C-preset-registry-pattern.md).

The AI director never passes inline component props. It passes **preset IDs**
like `scene.kinetic.scale_punch` or `trans.slide.left.fast`, which are resolved
against `src/registry/*` at render time. Adding a new variant = 4 lines in a
registry file, not a new component file.

---

## Phase 0 deliverable

> Empty-but-valid JSON → 5-sec black video uploaded to S3, callback fired.

Run `npm run smoke` with `.env` populated. See `scripts/smoke.ts`.

## Next phase

Phase 1 (MVP library, 2 weeks): real `StockFootageScene`, `KineticTypography`,
`CaptionOverlay`, `AudioMixer`, first 15 transitions, 15 animations. See
[`docs/B-build-plan.md`](./docs/B-build-plan.md).

---

## Notes

- Chromium + ffmpeg are baked into the Docker image.
- `RENDER_CONCURRENCY` controls BullMQ worker parallelism. Set based on VPS specs (see docs).
- `S3_PUBLIC_BASE_URL` is prepended to the object key for the callback URL — set to your CDN.
- `S3_FORCE_PATH_STYLE=true` for Cloudflare R2 / MinIO. `false` for AWS S3.
