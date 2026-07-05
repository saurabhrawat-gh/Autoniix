# Remotion Render Engine — Integration Contract

> Remotion lives in a separate repository: `yt-automation-remotion` (TypeScript).
> This document covers the integration contract between Temporal workflows and the Remotion render API.

---

## Repository Reference

| Property | Value |
|----------|-------|
| Repo | `yt-automation-remotion` |
| Path | `../yt-automation-remotion` |
| Language | TypeScript |
| API Port | 4000 |
| Queue | BullMQ (Redis-backed) |
| Storage | S3-compatible (MinIO) |
| Composition | `MainVideo` (16:9), `ShortFormVideo` (9:16), `ThumbnailComp` |

---

## How Temporal Calls Remotion

```
VideoProductionWorkflow
  └─ render_activity
       │
       ├─ 1. GET http://remotion:4000/api/health     (pre-flight check)
       ├─ 2. POST http://remotion:4000/api/render     (submit v3 JSON)
       ├─ 3. Poll GET /api/render/:id every 30s       (heartbeat to Temporal)
       └─ 4. When status=done → return video URL
```

### render_activity Implementation

```python
import httpx
import asyncio
from temporalio import activity

REMOTION_BASE = "http://remotion:4000"

@activity.defn
async def render_activity(v3_json: dict, channel_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Pre-flight health check
        health = await client.get(f"{REMOTION_BASE}/api/health")
        health_data = health.json()
        
        if health_data["status"] != "healthy":
            raise RuntimeError(f"Remotion unhealthy: {health_data}")
        
        if health_data["activeRenders"] >= health_data["maxConcurrent"]:
            raise RuntimeError("Remotion at capacity, will retry")

        # Submit render job
        composition = "MainVideo" if v3_json["meta"]["aspect"] == "16:9" else "ShortFormVideo"
        response = await client.post(
            f"{REMOTION_BASE}/api/render",
            json={
                "composition": composition,
                "inputProps": {"direction": v3_json},
                "codec": "h264",
                "outputFormat": "mp4",
                "quality": 80,
            },
        )
        render_data = response.json()
        render_id = render_data["renderId"]

        # Poll until complete (heartbeat to Temporal every iteration)
        while True:
            activity.heartbeat(f"Polling render {render_id}")
            await asyncio.sleep(30)

            status_resp = await client.get(f"{REMOTION_BASE}/api/render/{render_id}")
            status = status_resp.json()

            if status["status"] == "done":
                return {
                    "status": "success",
                    "data": {
                        "video_url": status["outputUrl"],
                        "file_size": status["fileSize"],
                        "render_duration_s": status["duration"],
                        "render_id": render_id,
                    },
                }
            elif status["status"] == "failed":
                raise RuntimeError(f"Render failed: {status.get('error')}")
```

---

## API Endpoints (consumed by Temporal)

### POST /api/render

**Request:**
```json
{
  "composition": "MainVideo",
  "inputProps": {
    "direction": {
      "version": "3.0",
      "meta": { "video_id": "...", "channel_id": "...", "title": "...", "duration_target_seconds": 480, "aspect": "16:9", "fps": 30, "resolution": { "width": 1920, "height": 1080 } },
      "template": "hybrid-kinetic",
      "theme": { },
      "grade_preset": "fx.grade.cinematic_teal_orange",
      "global_overlays": [],
      "audio_master": { },
      "segments": []
    }
  },
  "codec": "h264",
  "outputFormat": "mp4",
  "quality": 80
}
```

**Response:**
```json
{
  "renderId": "render_abc123",
  "status": "rendering",
  "estimatedDuration": 180
}
```

### GET /api/render/:id

**Response (in progress):**
```json
{
  "renderId": "render_abc123",
  "status": "rendering",
  "progress": 0.45
}
```

**Response (complete):**
```json
{
  "renderId": "render_abc123",
  "status": "done",
  "progress": 1.0,
  "outputUrl": "https://s3.example.com/yt-automation/renders/.../video.mp4",
  "duration": 145,
  "fileSize": 52428800
}
```

**Response (failed):**
```json
{
  "renderId": "render_abc123",
  "status": "failed",
  "error": "Composition render error: missing asset s3://..."
}
```

### POST /api/thumbnail

**Request:**
```json
{
  "composition": "ThumbnailComp",
  "inputProps": {
    "background_url": "https://s3.../dalle_bg.png",
    "title_text": "4 Types of Shivers",
    "title_style": { "font": "Montserrat", "weight": 900, "size": 120, "color": "#FFF" },
    "layout": "text_left_image_right",
    "accent_color": "#FF0000"
  },
  "format": "png",
  "width": 1280,
  "height": 720
}
```

**Response:**
```json
{
  "thumbnailUrl": "https://s3.../thumb.png"
}
```

### GET /api/health

**Response:**
```json
{
  "status": "healthy",
  "activeRenders": 1,
  "maxConcurrent": 3,
  "memoryUsage": "2.1GB / 8GB",
  "diskSpace": "12GB free"
}
```

---

## Direction Format v3 Contract

The v3 JSON schema is defined in the Remotion repo at `src/schemas/directionV3.ts` (Zod schema). The Assembly Service must produce JSON that passes this schema.

Key top-level fields:
- `version` — must be `"3.0"`
- `meta` — video metadata (id, channel, title, duration, aspect, fps, resolution)
- `template` — preset name from registry
- `theme` — colors, fonts
- `grade_preset` — color grading preset ID
- `global_overlays` — applied to all segments
- `audio_master` — background music config
- `segments[]` — frame-accurate scene definitions

See `docs/architecture/script-architecture.md` (View C) for the full schema and generation logic.

---

## Network Configuration

### Same Docker Network (1-5 channels)

When Remotion runs on the same VPS:

```yaml
# docker-compose.yml (main repo)
services:
  remotion:
    image: ghcr.io/your-org/yt-automation-remotion:latest
    ports: ["4000:4000"]
    networks: [yt-net]
    environment:
      - REDIS_URL=redis://redis:6379
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - S3_BUCKET=yt-automation
      - RENDER_CONCURRENCY=2
```

Services reference Remotion as `http://remotion:4000`.

### Separate VPS (5+ channels)

When Remotion runs on a dedicated render server:

1. Remotion VPS runs its own Docker Compose (from `yt-automation-remotion` repo)
2. Remotion VPS has its own Redis (for BullMQ queue)
3. Remotion VPS connects to shared MinIO (or its own MinIO synced to main)
4. Main services reference Remotion via IP/hostname: `http://render-vps:4000`
5. Secure with:
   - VPN (WireGuard) between VPSes, OR
   - Firewall rules allowing only main VPS IP on port 4000

```
env: REMOTION_BASE_URL=http://10.0.0.2:4000  # WireGuard VPN IP
```

---

## Scaling Render Capacity

| Channels | Remotion Setup | Concurrent Renders | VPS |
|----------|---------------|-------------------|-----|
| 1-3 | Same VPS, `RENDER_CONCURRENCY=1` | 1 | CX31 shared |
| 5-10 | Dedicated VPS | 2-3 | CX31 ($24) |
| 10-25 | Dedicated VPS, upgraded | 3-4 | CX41 ($36) |
| 25-50 | 2 render VPSes behind load balancer | 6-8 | 2× CX31 |
| 50-100 | 3-4 render VPSes | 9-12 | 3-4× CX31 |

Render time estimates (8-min long-form video):
- CX31 (4 vCPU, 8GB): 8-15 min per render
- CX41 (8 vCPU, 16GB): 5-10 min per render
- CX51 (16 vCPU, 32GB): 3-7 min per render
