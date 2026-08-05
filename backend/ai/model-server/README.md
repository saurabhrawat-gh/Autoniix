# Model Server (Phase 2C–2E)

GPU inference service for the four AI quality filters consumed by the
Remotion clip-filter pipeline:

| Endpoint kind  | Model                                                                     | Purpose                                  |
| -------------- | ------------------------------------------------------------------------- | ---------------------------------------- |
| `rife`         | [RIFE-v4.x](https://github.com/megvii-research/ECCV2022-RIFE)             | Optical-flow frame interpolation (warp)  |
| `scunet`       | [SCUNet](https://github.com/cszn/SCUNet)                                  | Real-image denoising                     |
| `real-esrgan`  | [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)                     | 2× / 4× super-resolution                 |
| `ddcolor`      | [DDColor](https://github.com/piddnad/DDColor)                             | B&W → colour                             |

## Protocol (matches `services/remotion/src/services/modelServerClient.ts`)

```
POST  /jobs              → { jobId }                          submit work
GET   /jobs/:jobId       → { status, outputUrl?, error? }     poll
POST  /jobs/:jobId/cancel→ { ok: true }                       best-effort
GET   /healthz           → 200 OK                             readiness
GET   /metrics           → Prometheus exposition              observability
```

Request body (`POST /jobs`):

```json
{
  "kind": "scunet" | "real-esrgan" | "rife" | "ddcolor",
  "inputUrl":     "https://minio:9000/raw/abc.mp4?X-Amz-...",
  "inputSha256":  "deadbeef…",
  "params":       { ... model-specific ... }
}
```

The server keys a content-addressed cache by
`sha256(inputSha256, kind, canonicalize(params), modelVersion)`. Cache hits
return `status="done"` synchronously from `POST /jobs`.

## Implementation notes

- Workers consume from a Redis stream (`model-jobs:<kind>`) and process one
  request at a time per GPU slot. Default 2 slots per A10G; one per RTX 4060.
- Models are loaded once at process start and pinned to GPU memory.
- Output files land in MinIO under `derived/<sha256>.mp4` and the URL is
  cached in Postgres (`clip_render_cache.rendered_url` from Phase 1E).
- Any failure → `status="failed"` + `error`; the orchestrator falls back to
  CPU equivalents listed in `FALLBACK_BY_KIND` in the TS client.

## Running locally (with GPU)

```bash
docker compose -f docker-compose.gpu.yml up model-server
```

`MODEL_SERVER_URL=http://localhost:8400` then makes the TS client switch to
real mode automatically. With the var unset (default in dev) every request
returns `{ status: "unavailable", fallback: "<cpuEquivalent>" }`.

## Status

- ✅ Protocol contract frozen (this README + `app.py` skeleton)
- ✅ TS client (stub + real modes)
- ⏳ Real implementation (RIFE, SCUNet, Real-ESRGAN, DDColor) — needs GPU host
