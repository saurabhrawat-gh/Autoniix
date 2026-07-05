# 08 — Implementation Plan

Concrete, phased execution plan from the current `services/remotion` state to the full system described in sections 2–7.

---

## 8.1 Phases at a glance

| Phase | Window | Theme | North-star |
| ----- | ------ | ----- | ---------- |
| P0 | Month 0–3 | Foundations | SceneGraph IR live, sharding working, diff cache warming, critic agent v1, MCP server, Python SDK, NVENC routing |
| P1 | Month 3–9 | Intelligence + scale | Tier 0/2 renderers, reframer, retention predictor, editor UX v1, templates, autoscaling, stems/ladder |
| P2 | Month 9–18 | Consolidation | Collab, advanced motion (Rive/Lottie/physics), RLHF, federated partial, marketplace beta |
| P3 | Month 18+ | Moonshot | Edge preview, regional mesh, match-cut, foundation-model adapter, enterprise + on-prem |

## 8.2 P0 — Foundations (0–3 months)

### Milestone P0.1 — SceneGraph IR landed

- `packages/scene-graph/` package scaffold (TS monorepo under `services/remotion/packages/` or new root `packages/` folder; pnpm workspace).
- Types in `types.ts` (section 02.3).
- `lower.ts`: `directionV3 → SceneGraph`. Unit tests against fixtures in `tests/fixtures/direction/*.json`.
- `hash.ts`: canonical JSON + sha256; property tests (`hash(normalize(x)) === hash(normalize(x'))` for equivalent graphs).
- `commit.ts`: pg writer to new `scene_graphs` table (schema in `scripts/init-db.sql`).

Deliverable: `lower(directionV3)` returns a SceneGraph that, when fed back through a trivial Tier-1 adapter, renders identical bytes to the current pipeline for 100 fixture videos. **This is the "refactor-is-safe" gate.**

Exit criteria: SSIM ≥ 0.99 between legacy render and lowered render on 100 fixtures.

### Milestone P0.2 — Frame-range sharding

- `services/remotion/src/api/flow.ts` wrapping BullMQ FlowProducer.
- `sharder.ts`: compute shard boundaries from SceneGraph segment boundaries + `-force_key_frames`.
- New queues: `render-tier1`, `render-concat`. Worker code split: `worker/shard.ts` + `worker/concat.ts`.
- Audio graph rendered at parent, muxed at concat.

Deliverable: a 10-min video renders in ~1/4 wall time with 4 shards; bit-identical to single-shard render.

### Milestone P0.3 — Diff cache

- `services/remotion/src/utils/cache.ts`: MinIO-backed, keyed by `hash(sub-scene-graph) + tierVersion + codec + resolution + fps`.
- Cache check before each shard dispatch.
- Cache write on shard success.
- TTL 30 days (configurable per channel).
- Metrics: `remotion_cache_hit_ratio{layer}`.

Deliverable: rerendering same video → ≥ 95% cache hit rate, <30 s total wall.

### Milestone P0.4 — Hardware encoder routing

- `utils/encoder.ts`: detect NVENC/QSV/VAAPI via `ffmpeg -encoders`.
- Route per env + job hint.
- CRF recalibration for NVENC.

Deliverable: H.264 1080p30 encode wall time drops 8×+ on NVENC-equipped worker.

### Milestone P0.5 — Bundle warmup + shared volume

- k8s RWX PVC `remotion-bundles`.
- `bundle-warmup` CronJob every 10 min (or on-deploy hook).
- Worker reads from volume first, bundles only on miss.

Deliverable: cold-start time 20 s → 1 s.

### Milestone P0.6 — Critic agent v1

- `packages/agents/critic.ts` with rubric in section 03.4.
- Uses GPT-4o vision for first cut; spec local-VLM swap in P1.
- Rubric-strict JSON output; Zod validates.
- Wired into post-render pipeline **after** `postRenderQc`: both must pass.

Deliverable: critic flags test rigs of 50 known-bad renders (10 black-flash, 10 text-overflow, 10 audio-drift, 10 color-drift, 10 stock-mismatch) with ≥ 85% precision.

### Milestone P0.7 — Repair agent v1

- `packages/agents/repair.ts` with rule table for the common 5 reasons.
- Only re-renders flagged shards (diff cache handles the rest).
- Bounded retry: max 2 repair loops per job.

Deliverable: critic-flagged jobs auto-heal at ≥ 70% rate without manual intervention on test fixtures.

### Milestone P0.8 — Director + Editor agents v1

- `packages/agents/director.ts`: algorithm in section 04.3.
- `packages/agents/editor.ts`: asset rerank (section 04.4) + pacing (section 04.6) + caption orchestration (section 04.5).
- Both are pure functions over SceneGraph + ctx; write patches, not direct mutations.
- Cost-capped, fallback to rule-based on budget exceed.

Deliverable: given 5 direction-v3 inputs per niche × 10 niches = 50 test cases, produce SceneGraphs that pass critic ≥ 90% first try.

### Milestone P0.9 — MCP server

- `services/remotion-mcp/` Node service.
- Tools per section 03.12: `propose_scene`, `render_preview`, `query_registry`, `get_qc_report`, `list_channels`, `get_retention_curve`, `run_bandit_sample`.
- Authed via the existing dashboard auth token.

Deliverable: external MCP client (Claude Desktop / Cursor) can end-to-end draft a scene-graph patch and trigger a preview render.

### Milestone P0.10 — Python SDK

- `sdk/python/yt_engine/` under repo root.
- Thin builder that emits direction-v3 and/or scene-graph JSON.
- Used by existing Python services (`script`, `brand`, `assembly`) to call the new flow.

Deliverable: one import swap in `src/temporal_workflows/video_production.py` replaces direct HTTP with typed SDK calls.

### Milestone P0.11 — Separate tier queues + KEDA

- `docker-compose.yml` split `remotion-worker` into `remotion-worker-t1` + `remotion-worker-concat`.
- For k8s: helm chart with KEDA triggers on BullMQ queue lengths.

Deliverable: scale from 1 to 8 workers on queue pressure inside 60s; scale down in 10 min.

### Milestone P0.12 — Cost + cache dashboards

- Grafana panels on `remotion_cost_usd_per_video`, cache hit ratios, critic pass rates, shard duration histograms.

Deliverable: one dashboard link answers "are we on budget this week?"

### P0 team + time

- **2 rendering engineers** (TS + ffmpeg + WebGPU prereqs)
- **1 ML / agents engineer** (Python + VLM + bandits)
- **1 systems / infra engineer** (k8s + Temporal + MinIO)
- **0.5 PM**
- Calendar: 12 weeks, ~60% headcount ramp.

### P0 risks & mitigations

| Risk | Mitigation |
| ---- | ---------- |
| SceneGraph refactor breaks existing renders | Bit-identical gate (SSIM ≥ 0.99) on 100 fixtures; legacy path stays hot-swappable for 4 weeks after cutover. |
| Critic false positives block good renders | Dual-gate (critic AND numeric QC both must pass or fail — never critic-alone blocks). Shadow mode for 2 weeks. |
| Diff cache false hits | Include versioned tier/codec/ffmpeg in key; canary runs compare cache-hit vs fresh. |
| NVENC unavailable on dev laptops | Encoder detection auto-falls back to libx264; CI matrix tests both. |

---

## 8.3 P1 — Intelligence + scale (3–9 months)

### P1.1 Tier 2 ffmpeg-direct renderer

- `worker/tier2.ts` with filter_complex templates per stock-only scene pattern.
- Lowerer tags clips `stock_only: true` when applicable.

### P1.2 Tier 0 WebGPU compositor (spike first, then committed)

- Weeks 1–4: research spike — port `Bloom`, `LUTGradeWebGL`, `ChromaticAberration`, `FilmGrain`, `ParticleSystem` to WebGPU shaders offscreen in Node via `@webgpu/dawn`.
- Weeks 5–8: NVENC zero-copy path (or fallback `rawvideo` pipe).
- Weeks 9–12: first production scenes route to T0 behind feature flag; A/B vs T1 for 2 weeks.

### P1.3 Reframer

- Saliency pipeline (CLIP + SAM2 keyframe sampling) → per-clip ROI trajectory → Kalman smooth → viewport keyframes.
- Caption re-flow to platform safe zones.
- Derived SceneGraphs for 9:16 / 1:1 / 4:5 with cache-hit assumption.

### P1.4 Retention predictor

- Window feature extractor (section 03.5).
- Per-niche XGBoost models trained on existing `video_outcomes` + backfilled YouTube Analytics.
- Editor queries before commit.

### P1.5 Cinematographer + Colorist + Sound agents

- Virtual camera node library (section 02.12).
- Colorist LUT adjustments per emotion + brand constraints.
- Beat detector + sidechain ducking as AudioGraph primitives.

### P1.6 Editor UX v1 in dashboard

- Next.js page: scene-graph tree view, per-node props panel, timeline ruler.
- Agent-suggestion diff panel.
- Real-time preview pane (WebRTC from preview compositor).
- Approval gate integrated with Temporal signals.

### P1.7 Templates + brand kits

- `templates` table (versioned SceneGraph presets per niche).
- Brand-kit editor UI bound to `brandDna`.

### P1.8 RLHF loop start

- For 5% of jobs, render two variants with different bandit arms.
- Dashboard reviewer picks preferred.
- Train preference model in parallel; not yet used for production until P2.

### P1.9 Autoscaling + Lambda burst

- KEDA live on all queues.
- Lambda burst path behind cost/SLA router.

### P1.10 Progressive upload + bitrate ladder + stems

- Multipart upload from ffmpeg stdout.
- Per-platform ladder fan-out.
- Stems already exist — wire to editor UI as "download for Premiere/Resolve".

### P1 deliverables

- End-to-end generation of 10-min long + 3-Shorts bundle in p95 8 min at $0.15.
- Critic pass rate ≥ 93% on first attempt.
- Reframer produces 9:16 with ≥ 90% retained ROI on 100 test videos.
- Editor UX usable by non-engineer test user.

### P1 team

- Add: **1 frontend engineer** (dashboard UX), **0.5 designer**.
- Rendering engineer specializing in GPU/WebGPU becomes critical — recruit early.

---

## 8.4 P2 — Consolidation (9–18 months)

- Multi-user collab via Yjs CRDT over SceneGraph.
- Rive + Lottie scene adapters.
- Physics + advanced motion primitives.
- RLHF in production — DPO on small editor LLM.
- Federated style learning (partial, per-tenant heads).
- Marketplace beta (scenes + templates first, agents in P3).
- Localization pipeline hardened (dubbing + language-specific captioning QA).
- SOC 2 Type I readiness; RBAC + SSO; audit log surfaced.
- Template marketplace MVP.

Team: add **1 ML engineer** (small models / DPO), **1 backend engineer** (marketplace + billing), **1 SRE**.

---

## 8.5 P3 — Moonshot (18+ months)

- Edge preview compositor (Fly.io / Cloudflare wasm).
- Multi-region render mesh.
- Match-cut suggester + visual continuity engine GA.
- 2D character rigs (Rive-driven) + phoneme-based lip-flap.
- Foundation-model video adapter (Sora-class behind `VideoGenProvider` ABC).
- Custom small agent model trained end-to-end on (SceneGraph, outcome).
- Enterprise on-prem AMI + helm chart hardened.
- Agent benchmark + leaderboard public.

---

## 8.6 Infrastructure stack (full)

- **Containers**: Docker + k8s (already in stack).
- **Orchestration**: Temporal (existing) for workflow; BullMQ (existing) for render queues.
- **DB**: Postgres + pgvector (existing) + Redis (existing).
- **Object store**: MinIO (existing) behind CDN for public egress.
- **Search**: pg full-text + pgvector for scene-graph similarity.
- **Observability**: Prometheus + Loki + Grafana (existing `observability/`).
- **CI/CD**: GitHub Actions (`.github/workflows/ci.yml` exists).
- **Secrets**: existing docker-compose env → sealed-secrets / Vault at scale.
- **Billing**: Stripe + usage events table.
- **Auth**: existing dashboard auth → add SAML/OIDC at enterprise.

## 8.7 AI stack

- **LLMs**: GPT-4o, Claude Sonnet (direction + editor critic at first); Qwen2-VL / InternVL local VLM for cost.
- **Embeddings**: `all-MiniLM-L6-v2` (already used in research service) + CLIP ViT-L/14 for visual.
- **Models**: XGBoost for retention + render-fail; isotonic calibration; Thompson bandits; small DPO-tuned editor LLM in P2.
- **Vector store**: pgvector (existing).
- **Fine-tuning infra**: modal.com or Lambda Labs for occasional; AWS SageMaker if enterprise.

## 8.8 Media pipeline stack

- ffmpeg (static build in container).
- `@remotion/renderer` (existing).
- `@remotion/bundler` (existing).
- `@webgpu/dawn` or `wgpu-native` rust binding (P1).
- librosa (Python) or `web-audio-beat-detector` (JS) for beats.
- `whisper-timestamped` for forced alignment (if not already upstream in voice service).
- `face-api.js` / `insightface` if talking-head support comes later.

## 8.9 Cost estimation (fully loaded at 1k videos/day)

```
Compute (k8s spot + GPU):
  t1 workers (10 × c6i.2xlarge spot)    ≈ $700/mo
  t2 workers (6 × c6i.xlarge spot)       ≈ $200/mo
  t0 workers (3 × L4 on-demand)          ≈ $1500/mo
  concat (2 × c6i.large)                 ≈ $100/mo
  API + preview + MCP (3 × c6i.large)    ≈ $150/mo
Postgres + Redis + MinIO (self-hosted, 1 × c6i.4xlarge + 8TB EBS) ≈ $800/mo
CDN egress (~ 1 TB/day) ≈ $500/mo
AI API (GPT-4o + VLM, 1k videos × ~$0.12 each)  ≈ $3600/mo
Logging + metrics infra                         ≈ $200/mo
──────────────────────────────────────
Total: ≈ $7,750/mo  →  $0.26 per video at 1000/day (30k/mo)
```

With diff cache warm (6 months of channels running): drops to **~$0.15/video**.
With local VLM routing: drops to **~$0.11/video**.

## 8.10 Skills required

| Phase | Critical skills |
| ----- | --------------- |
| P0 | TS + Node, BullMQ, ffmpeg, Remotion internals, Zod, pg, k8s, VLM prompt engineering |
| P1 | WebGPU, CUDA/NVENC basics, React (editor UX), Kalman filtering, CLIP/SAM adapting |
| P2 | CRDTs (Yjs), small-model fine-tuning (DPO), federated learning, marketplace backend |
| P3 | Edge compute (wasm WebGPU), rust (wgpu), foundation-model adapters, enterprise sales eng |

## 8.11 Hiring plan

```
Now (P0)       +1 rendering eng, +1 infra eng, +1 ML eng, +0.5 PM
Month 3 (P1)   +1 frontend eng, +0.5 designer
Month 9 (P2)   +1 ML eng (small models), +1 backend (marketplace), +1 SRE
Month 18 (P3)  +2 research eng, +1 enterprise SE, +1 security lead
```

Total at 24 months: ~12 engineers + 1–2 non-eng.

## 8.12 Execution discipline

- **Scene Graph is sacred**. No feature lands without going through it. No agent writes outside it.
- **Dual-gate all agent outputs**: numeric QC + agent check; neither alone can pass/fail.
- **Every new primitive ships a cache key**. No uncacheable ops.
- **Every new agent declares cost budget**. No unbounded LLM calls.
- **Bit-identical refactors**: SSIM floor on canary renders for any engine change.
- **Feature flags per tier / agent / cache layer**. Kill switches in dashboard.

## 8.13 Success definition for each phase

| Phase | Pass conditions |
| ----- | --------------- |
| P0 | 4× throughput vs today; critic+QC dual-gate live; MCP server used by ≥1 external agent in dogfood; $/video ≤ $0.30. |
| P1 | Reframer ships; retention model live and driving ≥ 1 publicly visible uplift; editor UX used daily by an internal creator; $/video ≤ $0.18; 1k videos/day headroom. |
| P2 | Collab + marketplace beta; RLHF in production; 10× videos/day over P1; 3 enterprise logos. |
| P3 | Regional mesh in 2 regions; foundation-model adapter live; agent benchmark public; >100 certified third-party agents. |

## 8.14 First 30 days of P0 (concrete)

Week 1:
- Create `packages/scene-graph/` workspace.
- Write `types.ts` + `hash.ts` + test harness.
- Stand up `scene_graphs` pg table migration.

Week 2:
- Implement `lower(directionV3)`.
- 100-fixture bit-identical gate; SSIM harness in CI.
- Land `packages/scene-graph/` v0.1 behind feature flag.

Week 3:
- `services/remotion/src/api/flow.ts` with FlowProducer.
- Split worker queues; parent concat job.
- Bench sharded vs single on 10 fixtures.

Week 4:
- `utils/cache.ts` MinIO diff cache.
- Instrument `remotion_cache_hit_ratio`.
- Dogfood on this repo's own channels.

By end of month 1: demonstrable 3–4× throughput gain on existing content, zero quality regression, caching validated.

---

## 8.15 Summary

This is not a rewrite. It is a **layering strategy**: every current primitive (bundle cache, registry, postRenderQc, direction-v3, `renderMedia`) stays in place and is wrapped by a new control surface (SceneGraph IR + agents + sharder + critic). The existing Temporal workflow at `@/home/saurabh/Desktop/YouTube/youtube-automation/src/temporal_workflows/video_production.py` gains one new phase (4.5) and otherwise keeps its shape.

Start with SceneGraph IR + sharding + diff cache + critic agent + NVENC routing in P0. Everything else — reframer, tier 0/2, retention, RLHF, collab, marketplace — composes on top with no foundation changes after that.

The engine is the **orchestration of Remotion**, not a replacement of Remotion. Ship that thesis end-to-end in 3 months, then compound.
