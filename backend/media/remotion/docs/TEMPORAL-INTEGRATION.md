# Temporal Integration Guide

> How the Temporal orchestrator (from `yt-automation-n8n`) calls this Remotion render service.

---

## Overview

The Temporal `render_activity` in the main platform repo calls this service's HTTP API to render videos and thumbnails. The flow:

1. **Health check:** `GET /api/health` — verify capacity
2. **Submit job:** `POST /api/render` — enqueue Direction v3 JSON
3. **Poll status:** `GET /api/render/:id` — every 30s (Temporal heartbeats while waiting)
4. **Retrieve output:** `outputUrl` in status response → video uploaded to S3/MinIO

---

## Expected Request Payloads

### Video Render

```json
{
  "composition": "MainVideo",
  "inputProps": {
    "direction": {
      "version": "3.0",
      "meta": {
        "video_id": "VID_BS001_20250425_001",
        "channel_id": "BS001",
        "title": "4 Types of Shivers",
        "duration_target_seconds": 480,
        "aspect": "16:9",
        "fps": 30,
        "resolution": { "width": 1920, "height": 1080 }
      },
      "template": "hybrid-kinetic",
      "theme": { "primary_color": "#FF3B30", "accent_color": "#FFD60A", "background_color": "#000", "text_color": "#FFF", "fonts": { "heading": "Inter", "body": "Inter" } },
      "grade_preset": "fx.grade.cinematic_teal_orange",
      "global_overlays": [
        { "type": "vignette", "intensity": 0.3 },
        { "type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15 }
      ],
      "audio_master": { "music_url": "s3://...", "music_volume": 0.15, "ducking": true, "ducking_threshold": -20 },
      "segments": []
    }
  },
  "codec": "h264",
  "outputFormat": "mp4",
  "quality": 80
}
```

- `composition`: `"MainVideo"` (16:9) or `"ShortFormVideo"` (9:16)
- `inputProps.direction`: Full Direction v3 JSON (validated against `src/schemas/directionV3.ts`)
- `codec`: `"h264"` (default) or `"h265"` for smaller files
- `quality`: 1-100 (80 recommended)

### Thumbnail Render

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

---

## Callback Contract

When `callbackUrl` is provided in the render request, the worker POSTs to it on completion:

### Success

```json
{
  "renderId": "render_abc123",
  "status": "done",
  "outputUrl": "https://s3.example.com/yt-automation/renders/.../video.mp4",
  "fileSize": 52428800,
  "duration": 145
}
```

### Failure

```json
{
  "renderId": "render_abc123",
  "status": "failed",
  "error": "Composition render error: missing asset s3://..."
}
```

**Note:** The Temporal integration uses **polling** (not callbacks) because Temporal activities need to heartbeat. The `callbackUrl` field is optional and not used by the Temporal render_activity.

---

## Environment Variables for Service Discovery

When running alongside Temporal services (same Docker network):

```env
# Already in .env — no changes needed for these
REDIS_URL=redis://redis:6379
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=yt-automation
S3_PUBLIC_BASE_URL=https://s3.yourdomain.com/yt-automation

# Render settings
RENDER_CONCURRENCY=2       # Match to VPS vCPU count / 2
PORT=4000                  # API port
```

When running on a **separate VPS**:

```env
# MinIO/S3 must be reachable from this VPS
S3_ENDPOINT=http://10.0.0.1:9000    # Main VPS MinIO via VPN
# OR use a public MinIO endpoint with TLS

# Redis is local to this VPS (separate from main Redis)
REDIS_URL=redis://localhost:6379
```

---

## Health Check Expectations

Temporal's `render_activity` calls `GET /api/health` before submitting a job.

**Expected response:**
```json
{
  "status": "healthy",
  "activeRenders": 1,
  "maxConcurrent": 3,
  "memoryUsage": "2.1GB / 8GB",
  "diskSpace": "12GB free"
}
```

**Pre-flight rules (enforced by Temporal activity):**
- `status` must be `"healthy"`
- `activeRenders` must be `< maxConcurrent`
- If either fails → Temporal retries with backoff (up to 2 attempts)

---

## Docker Network Setup

### Same VPS (added to main docker-compose.yml)

```yaml
services:
  remotion:
    image: ghcr.io/your-org/yt-automation-remotion:latest
    ports: ["4000:4000"]
    networks: [yt-net]
    depends_on: [redis, minio]
    environment:
      - REDIS_URL=redis://redis:6379
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - S3_BUCKET=yt-automation
      - RENDER_CONCURRENCY=2
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "4"
```

### Separate VPS

Run this repo's own `docker-compose.yml` on the render VPS. Connect to main MinIO via VPN or public endpoint.
