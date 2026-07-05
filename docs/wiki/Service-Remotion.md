# Service: Remotion (Render Engine)

## Purpose

The TypeScript render engine — a separate codebase under
`services/remotion/` built into the Autoniix stack via two (or six)
Docker services. Receives a `RenderConfig` from the assembly service via
BullMQ, renders frames in headless Chromium, encodes with ffmpeg, and
uploads the MP4 to MinIO.

## Source

- `services/remotion/` (separate repo: `yt-automation-remotion`)
- `docker-compose.yml:380-563`

## Services

| Container | Memory | Profile | Role |
|---|---|---|---|
| `remotion-api` | 2G | default | Express API, BullMQ producer |
| `remotion-worker` | 4G | default | Single Chromium renderer |
| `remotion-worker-tier1` | 4G | `vision` | Creative-heavy renders (concurrency 2) |
| `remotion-worker-tier2` | 2G | `vision` | High-volume renders (concurrency 4) |
| `remotion-worker-concat` | 1G | `vision` | Final concat pass (concurrency 2) |
| `remotion-mcp` | 512M | `vision` | MCP server on `:4100` for AI-assisted edits |

## API endpoints

| Method + Path | Purpose |
|---|---|
| `POST /api/render` | Enqueue render job, returns `jobId` |
| `GET  /api/render/:id` | Job status (queued/active/completed/failed) |
| `GET  /api/health` | Liveness |

## Storage layout

Rendered output goes to:

```
s3://autoniix/<S3_KEY_PREFIX>/renders/<jobId>/output.mp4
```

`S3_KEY_PREFIX` is driven by `ENVIRONMENT_MODE` (`test`/`prod`).

## Diff cache (vision profile)

Tier-aware workers share a `remotion_bundle_cache` volume so the webpack
bundle is reused across renders. Combined with `DIFF_CACHE_ENABLED=true`,
identical scenes can hit the cached frame buffer and save ~40% of render
time on series-style content.

## Related pages

- [[Service-Assembly]] · [[Architecture-Container-Topology]]
- Vision docs: `docs/future/remotion-vision/`
