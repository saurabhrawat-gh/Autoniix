# 05 — Performance & Scale

How to take the architecture of sections 2–4 from one worker to a global render mesh capable of 10k+ videos/day at predictable cost and latency.

---

## 5.1 Scale targets

| Tier | Videos / day | p95 latency (10-min long) | $/video target |
| ---- | ------------ | ------------------------- | -------------- |
| Dev | 10 | 20 min | n/a |
| Solo creator | 100 | 15 min | $0.25 |
| Studio | 1 000 | 12 min | $0.15 |
| Network | 10 000 | 10 min | $0.10 |
| Platform | 100 000 | 8 min | $0.06 |

Current single-worker throughput: ~30 videos/day at $0.40–1.10/video.

## 5.2 Rendering parallelism hierarchy

```
Job (1 video)
 └─ Shards (frame-range parallelism, 4–32 per video)
     └─ Frames (per-tier intra-shard parallelism)
         └─ Tier 0: WebGPU dispatch groups per frame
         └─ Tier 1: Chromium page pool (RENDER_CONCURRENCY)
         └─ Tier 2: ffmpeg threads + filter graph
     └─ Encoder (NVENC/QSV/VAAPI parallel per shard)
 └─ Parent concat (1, post-shards)
```

Three orthogonal knobs:

1. Shards per job (sharder)
2. Intra-shard concurrency (tier-specific)
3. Jobs per node (worker instances)

## 5.3 Distributed render with BullMQ FlowProducer

```ts
// illustrative — services/remotion/src/api/flow.ts
import { FlowProducer } from "bullmq";
const flow = new FlowProducer({ connection });

await flow.add({
  name: "concat",
  queueName: "render-concat",
  data: { renderId, audioGraph, shardBoundaries },
  children: shards.map((s) => ({
    name: "shard",
    queueName: tierQueue(s.tier), // "render-tier0" | "render-tier1" | "render-tier2"
    data: { renderId, shardId: s.id, sceneGraph: s.graph, range: s.range, tier: s.tier },
  })),
});
```

Parent runs only after all children return; on child failure, parent fails (with backoff) and surfaces shard-level error to the repair loop.

## 5.4 Kubernetes topology

```
Namespace: remotion
  Deployment: remotion-api        (2 replicas, HPA cpu)
  Deployment: remotion-worker-t0  (GPU nodeSelector, KEDA on queue "render-tier0")
  Deployment: remotion-worker-t1  (CPU, KEDA on "render-tier1")
  Deployment: remotion-worker-t2  (CPU fast, KEDA on "render-tier2")
  Deployment: remotion-preview    (GPU, session-pinned)
  Deployment: remotion-concat     (CPU, KEDA on "render-concat")
  CronJob: bundle-warmup          (every 10 min, primes bundle cache volume)
  StatefulSet: redis-bullmq       (existing)
  StatefulSet: minio              (existing)

  Node pools:
    - cpu-spot-large  (t1/t2 workers, spot, c6i.4xlarge equiv)
    - gpu-ondemand-l4 (t0 workers, L4 for WebGPU + NVENC, on-demand)
    - cpu-concat      (c6i.xlarge, on-demand, small count)
```

KEDA scales on `bullmq` queue length with cooldown; HPA backup on CPU/mem.

## 5.5 Serverless burst (Lambda)

Remotion Lambda exists upstream — use it as a **burst** path, not primary:

- When queue depth > 3× baseline capacity for > 2 min and SLA is at risk → route new jobs to Lambda path.
- Lambda is Tier-1-only (no WebGPU). Cost is higher per render-min but no capacity wait.
- Cost-aware dispatcher chooses Lambda vs k8s based on $ SLA per job.

```
dispatch_decision(job):
  if deadline.remaining < p95(tier) * 1.5 and k8s_queue_full:
    return "lambda"
  elif job.tier == "t0" and gpu_free > 0:
    return "k8s-t0"
  ...
```

## 5.6 Queue design

Separate queues so one noisy tier doesn't block others:

```
render-tier0     (GPU shards)           concurrency=N_GPU
render-tier1     (CPU Chromium shards)  concurrency=N_CPU
render-tier2     (ffmpeg shards)        concurrency=N_FAST
render-concat    (parent jobs)          concurrency=N_CONCAT
render-preview   (interactive)          priority > batch
thumbnail        (cheap stills)         concurrency high
```

Priority weighting: interactive preview > customer publish > backfill.

## 5.7 Cache hierarchy

| Layer | Key | Hit ratio target | Store |
| ----- | --- | ---------------- | ----- |
| Bundle cache | content hash of `src/` tree | 99% | shared RO volume + fallback bundle on miss |
| Asset cache | sha256 of URL+transform | 90% | MinIO `assets/` + CDN edge |
| Frame cache (diff) | sub-scene-graph hash + tier version | 60–80% after warm | MinIO `frames/` |
| Encoded shard cache | shard hash + encoder config | 40–60% | MinIO `shards/` |
| Critic cache | frame strip hash + rubric version | 70% | pg `critic_reports` |

Cache invalidation on renderer/agent version bump: bump version in key, old entries age out with TTL.

## 5.8 Bundle warmup + shared volume

`cachedBundle` in worker is currently per-process. Upgrade:

1. Compute bundle content hash (sha256 of `src/**` + deps).
2. Store bundle output at `bundles/{hash}/` on a shared RO volume (k8s RWX PVC or S3 mount).
3. Worker checks volume first, bundles only on miss.
4. `bundle-warmup` CronJob pre-bundles after any deploy.

Result: worker cold-start goes from ~20 s to ~1 s.

## 5.9 Progressive upload

Today the full MP4 is written to temp, then uploaded. For long videos that's dead time.

Upgrade: pipe ffmpeg stdout to MinIO multipart upload with 8 MiB parts. Upload finishes ~same time as encode.

```ts
const upload = minio.newMultipart("renders/xxx.mp4");
ffmpeg.stdout.on("data", (chunk) => upload.push(chunk));
ffmpeg.on("close", () => upload.complete());
```

## 5.10 Adaptive bitrate ladder

Per-platform ladder, generated once from master H.264:

```
Master (CRF 18, 1080p)
 ├─ 1080p @ 8 Mbps  (YouTube)
 ├─  720p @ 4 Mbps  (YouTube fallback, Shorts-16:9)
 ├─  480p @ 2 Mbps
 └─  360p @ 1 Mbps
```

ffmpeg `-b:v` forced + `-preset fast` for ladder runs; ~15% of master encode cost each.

## 5.11 Scene-level rendering & incremental publish

For very long-form (podcast / documentary 30+ min): render + publish **sections** progressively:

- Shards become the publish unit; the parent can emit partial results to a preview URL after each shard completes.
- Not relevant for YouTube upload (atomic), highly relevant for dashboard preview.

## 5.12 Frame deduplication across jobs

Two channels each produce a hook using `StockFootageScene{queries:["mountain sunrise"]}` with the same asset (sha256 match) and same transforms (fit/duration/LUT). Diff cache **must hit** — identical scene-graph sub-tree → same hash.

This is pure win: for evergreen stock usage, 5–15% of total frames are duplicates across the fleet after 2 weeks of warm cache.

## 5.13 Intelligent scheduling

Signals the scheduler uses:

- **Per-shard predicted cost** (render_predictor → ms + $).
- **Tier availability** (GPU queue depth + node pool capacity).
- **SLA deadline** (job deadline - now).
- **Cost budget remaining** for the channel/day.
- **Warm bundle locality** (prefer workers that already have this bundle hash warm).

Policy: greedy-assign, EDF (earliest-deadline-first), with cost ceiling per job.

## 5.14 Edge rendering (future)

For creator previews: push a lightweight Tier-0 compositor to Cloudflare Workers (wasm WebGPU stub) or Fly.io regional nodes. Only interactive preview — not final render.

- 200 ms round-trip anywhere in the world for a 3-second preview.
- Real-time collaboration becomes tractable.

## 5.15 Cost model

Per-shard unit cost approximation:

| Tier | Cost/render-min ($, 1080p30, spot) |
| ---- | ------------------------------------ |
| T0 (L4 + NVENC) | 0.006 |
| T1 (c6i.2xl, 8 vCPU) | 0.012 |
| T2 (ffmpeg direct, c6i.xl) | 0.003 |
| Lambda burst | 0.020 |

For a 10-min video with 60% T1 / 30% T2 / 10% T0:

```
wall_min * $/min with 4-way shard:
  10 min / 4 shards * 60% * $0.012 = $0.018  (T1 share)
  10 min / 4 shards * 30% * $0.003 = $0.0022 (T2 share)
  10 min / 4 shards * 10% * $0.006 = $0.0015 (T0 share)
  + NVENC encode ladder ~ $0.003
  + MinIO egress ~ $0.002
  + agent LLM cost (critic + editor) ~ $0.08–0.15
  ─────────────────────────────
  TOTAL ~ $0.11–0.18 per 10-min
```

With diff cache warm (repeat channel): render portion drops ~50%.

## 5.16 Autoscaling signals

KEDA triggers:

```yaml
# illustrative
triggers:
  - type: redis
    metadata:
      address: redis:6379
      listName: bull:render-tier1:waiting
      listLength: "5"
  - type: prometheus
    metadata:
      query: histogram_quantile(0.95, rate(remotion_render_duration_seconds_bucket[5m]))
      threshold: "600"  # p95 > 10 min → scale
```

Scale-down cooldown 10 min; spot node replacement handled by k8s cluster autoscaler.

## 5.17 Observability for performance

Metrics to expose via Prometheus (already wired in stack under `observability/prometheus.yml`):

- `remotion_render_duration_seconds{tier,composition}` (histogram)
- `remotion_shard_duration_seconds{tier}`
- `remotion_queue_depth{queue}`
- `remotion_cache_hit_ratio{layer}` (bundle, asset, frame, shard)
- `remotion_encoder{encoder}` (counter by encoder used)
- `remotion_critic_pass_rate`
- `remotion_repair_loops{result}`
- `remotion_cost_usd_per_video`

Grafana dashboards extend `observability/grafana/dashboards/`.

## 5.18 SLOs

| SLO | Target | Error budget (monthly) |
| --- | ------ | ---------------------- |
| Render p95 | ≤ 12 min (10-min long) | 1% |
| QC pass on first attempt | ≥ 95% | 5% |
| Critic pass after ≤ 2 repair loops | ≥ 99% | 1% |
| Lambda burst usage | ≤ 10% of traffic | 10% |
| $/video | ≤ $0.18 at 1k/day | 15% |

Alerting rules tie to these SLOs with multi-window burn-rate thresholds.

## 5.19 Chaos & resiliency

- Kill 1 GPU node during render — shards failover to CPU tier via router; diff cache ensures no duplicate work.
- Redis failover — BullMQ resumes from persisted state; in-flight jobs retried.
- MinIO partition — assets fetched from upstream provider (Pixabay/Pexels/Envato) as fallback; agents degrade to smaller asset set.
- Bundle cache corruption — worker bundles fresh, logs anomaly, CI rebuilds canonical.

## 5.20 Capacity planning

For 10k videos/day at 10-min avg:

```
Total render-minutes/day ≈ 10000 * 10 / 4 (shards) ≈ 25000 render-min/day
Useful wall hours = 24 * 0.8 = 19 hr → 1140 min
Required parallel workers ≈ 25000 / 1140 ≈ 22 workers
Mix: 10 T1 + 8 T2 + 3 T0 + 1 concat, headroom 20%
```

Storage: 10k × 200 MB master + ladder ≈ 3 TB/day MinIO write, ≈ 90 TB/month, assume 30-day retention + S3 glacier after.

Network egress: 10k × 500 MB delivery payload ≈ 5 TB/day. Use CDN for public delivery.

## 5.21 Cost optimization toolkit

Cross-references existing savings loop:

- Tier routing: est. -40% vs all-T1
- Diff cache: est. -25% after 2-week warmup
- NVENC where applicable: -50% encode time, -20% encode cost
- Local VLM for critic: est. -80% vs API VLM on pass-through cases
- Bandit-driven effect simplification for low-risk channels: -10%
- Asset dedup (perceptual hash): -5%

Combined vs current naive single-tier pipeline: **-60 to -70% cost** at scale.

Next: section 06 — the exhaustive feature catalog.
