# 06 — Feature Catalog

Exhaustive, anchored feature list. Each row includes: **why it matters**, **implementation sketch**, **difficulty** (S=small, M=medium, L=large, XL=research), **impact** (★ low to ★★★★★ critical), **priority** (P0 now → P3 moonshot).

Grouped for scanability. Every row references a concrete extension surface in this repo.

---

## 6.1 Rendering engine

| # | Feature | Why | Implementation sketch | Diff | Impact | Pri |
| - | ------- | --- | --------------------- | ---- | ------ | --- |
| R01 | Scene Graph IR | Enables agents, cache, reframer | new `packages/scene-graph/`; lower from `directionV3` | L | ★★★★★ | P0 |
| R02 | Frame-range sharding | 4–8× throughput | BullMQ `FlowProducer` wrapping `renderQueue` | M | ★★★★★ | P0 |
| R03 | Diff render cache | 25–50% cost cut | MinIO `frames/{hash}.mp4` + lookup before dispatch | M | ★★★★★ | P0 |
| R04 | Hardware encoder routing | 10× encode speed | detect NVENC/QSV/VAAPI in `worker/renderer.ts` | S | ★★★★ | P0 |
| R05 | Tier 2 ffmpeg-direct renderer | 20–100× on stock segments | new `worker/tier2.ts` | M | ★★★★ | P1 |
| R06 | Tier 0 WebGPU compositor | 5–50× on shader scenes | `@webgpu/dawn` bindings + shader lib mirroring `registry/effects.ts` | XL | ★★★★★ | P1 |
| R07 | Progressive multipart upload | cut dead time | pipe ffmpeg stdout → MinIO multipart | S | ★★ | P1 |
| R08 | Bundle warmup + shared volume | cold start 20s→1s | k8s RWX PVC + CronJob | S | ★★★ | P0 |
| R09 | Capability router | cost-aware tier dispatch | lowerer tags clips; dispatcher picks tier | M | ★★★★ | P0 |
| R10 | Render sandbox (OOM/timeout) | stability at scale | per-job cgroup limit + watchdog | S | ★★★ | P1 |
| R11 | Keyframe authoring layer | motion-graphics parity | `Keyframe[]` node + interpolator library (spring/bezier/quad) | M | ★★★★ | P1 |
| R12 | Time remap / speed ramps | stylistic range | scene-graph `speed` node + Remotion `playbackRate` | M | ★★★ | P2 |
| R13 | Optical-flow morph between scenes | cinematic transitions | RAFT/GMA optical flow + warp shader | XL | ★★★ | P3 |
| R14 | Depth-map parallax | 2.5D feel on stills | MiDaS depth → 3 planes → camera push | L | ★★★ | P2 |
| R15 | Adaptive bitrate ladder | platform fit | ffmpeg fan-out per ladder | S | ★★★ | P1 |

## 6.2 Animation & motion

| # | Feature | Why | Implementation sketch | Diff | Impact | Pri |
| - | ------- | --- | --------------------- | ---- | ------ | --- |
| A01 | Shared motion primitives library | consistency + reuse | wrap Motion One / framer into `components/motion/` | S | ★★★ | P1 |
| A02 | Physics primitives (spring nets, cloth) | expressive micro-animation | rapier/matter.js adapter; deterministic seed | L | ★★ | P2 |
| A03 | Lottie adapter as Scene clip | unlock designer output | `components/scenes/LottieScene.tsx` | S | ★★★★ | P0 |
| A04 | Rive adapter | interactive motion graphics | `components/scenes/RiveScene.tsx` | M | ★★★ | P1 |
| A05 | Motion interpolation between shots | 60fps feel on 30fps | RIFE/FILM adapter, post-shard | L | ★★ | P2 |
| A06 | Virtual camera system | cinematic language | `CameraNode` in scene graph (section 02.12) | M | ★★★★ | P1 |
| A07 | Motion matching library | natural camera push/pull | rule table per scene archetype | S | ★★★ | P1 |
| A08 | Character rigs (2D) | 2D animated explainers | Rive + lip-flap from phonemes | L | ★★★ | P2 |
| A09 | Hand-drawn animation cel system | style differentiation | procedural frame-hold + boil shader | XL | ★★ | P3 |

## 6.3 AI integrations

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| I01 | Director agent | skeleton plan | `packages/agents/director.ts` | M | ★★★★★ | P0 |
| I02 | Editor agent | B-roll, cuts, captions | `packages/agents/editor.ts` | L | ★★★★★ | P0 |
| I03 | Cinematographer agent | cameras, pacing | `packages/agents/cine.ts` | M | ★★★★ | P1 |
| I04 | Colorist agent | per-segment LUT/tint | `packages/agents/colorist.ts` + `lutLibrary` | M | ★★★ | P1 |
| I05 | Sound designer agent | music/SFX/ducking | `packages/agents/sound.ts` | M | ★★★★ | P1 |
| I06 | Vision critic agent | render QC beyond numbers | VLM wrapper + rubric schema | M | ★★★★★ | P0 |
| I07 | Repair agent | localized re-render | rule table + LLM fallback | M | ★★★★ | P0 |
| I08 | Retention predictor | pacing decisions | GBM over window features | M | ★★★★★ | P1 |
| I09 | Render-fail predictor | avoid doomed renders | extend `render_predictor.py` | S | ★★★★ | P0 |
| I10 | Style learner per channel | personalization | per-channel priors table + bandits | M | ★★★★ | P1 |
| I11 | Brand consistency checker | no drift | CLIP embedding distance | S | ★★★ | P1 |
| I12 | Copyright pHash + SynthID | legal safety | local hash DB + upstream checks | M | ★★★★★ | P0 |
| I13 | NSFW / moderation classifier | platform safety | upstream API + local fallback | S | ★★★★ | P0 |
| I14 | AI B-roll planner | density + relevance | NER + CLIP rerank (section 04) | M | ★★★★ | P0 |
| I15 | AI stock footage rerank | better cuts | CLIP + pHash novelty | S | ★★★★ | P0 |
| I16 | AI subtitle styling | emotion-aware captions | style table + critic legibility check | S | ★★★ | P1 |
| I17 | AI music selection bandits | per-channel fit | arm table per library | S | ★★★ | P1 |
| I18 | AI hook generator | retention in first 3s | N-variant render + critic selection | M | ★★★★★ | P0 |
| I19 | Visual continuity engine | palette stability | scene-graph color walk + diff | M | ★★ | P2 |
| I20 | AI scene repair (VLM-driven) | fix bad frames | VLM patch proposal → limited-tool mutation | L | ★★★ | P2 |
| I21 | AI character consistency | for stylized 2D | LoRA + reference embedding | L | ★★ | P3 |
| I22 | MCP server | external agent access | tools per section 03.12 | S | ★★★★ | P0 |
| I23 | RLHF preference loop | learn from reviews | pairwise + DPO on small editor LLM | L | ★★★ | P2 |
| I24 | Local VLM for critic | cost control | Qwen2-VL / InternVL on GPU pool | M | ★★★★ | P1 |
| I25 | Federated style learning | multi-tenant privacy | FedAvg on retention backbone | XL | ★★ | P3 |

## 6.4 Cloud / infrastructure

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| C01 | Separate tier queues | isolation | t0/t1/t2/concat BullMQ queues | S | ★★★★ | P0 |
| C02 | KEDA autoscaling | elastic capacity | triggers on queue + p95 | S | ★★★★ | P0 |
| C03 | Lambda burst path | SLA safety | Remotion Lambda behind router flag | M | ★★★ | P1 |
| C04 | Regional render mesh | global latency | multi-region k8s; geo-routed API | L | ★★ | P3 |
| C05 | Edge preview compositor | collab UX | wasm WebGPU at edge | XL | ★★ | P3 |
| C06 | Signed-URL CDN for assets + output | delivery perf | CloudFront/BunnyCDN in front of MinIO | S | ★★★ | P1 |
| C07 | Cost-aware dispatcher | $ optimization | linear program over tier $/min + SLA | M | ★★★ | P1 |
| C08 | Chaos harness | resiliency | litmus + scheduled drills | S | ★★ | P2 |
| C09 | Render replay | debugging | store scene-graph + bundle hash per job; one-click replay | S | ★★★ | P1 |
| C10 | A/B render harness | experimentation | render two variants, diff outputs | M | ★★★ | P1 |

## 6.5 Editor UX / no-code tools

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| U01 | Dashboard scene-graph editor | creator control | Next.js page tree view + drag-reorder | M | ★★★★ | P1 |
| U02 | Real-time preview panel | creator trust | WebRTC from preview compositor | M | ★★★★★ | P1 |
| U03 | Agent suggestion panel | "AI wrote this — accept?" | diff view over scene graph | S | ★★★★ | P1 |
| U04 | Per-scene timing flamegraph | perf insight | timing sidecar from renderer | S | ★★ | P2 |
| U05 | Timecoded review comments | team workflow | pg table + UI annotations | S | ★★ | P2 |
| U06 | Approval gate in workflow | QA | Temporal signal from dashboard | S | ★★★ | P1 |
| U07 | Template marketplace UI | creator onboarding | curated scene-graph templates | M | ★★★ | P2 |
| U08 | Prompt → preview creator flow | copilot UX | chat panel binds to MCP tools | M | ★★★★ | P1 |
| U09 | Version history / diff view | safety net | pg `scene_graphs` revisions | S | ★★★ | P1 |
| U10 | Visual capability legend | "which scenes can run on tier 0?" | static doc + dashboard tooltip | S | ★ | P2 |

## 6.6 Collaboration

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| CO1 | Multi-user concurrent edit | team use | Yjs CRDT over scene graph | L | ★★★ | P2 |
| CO2 | Comments + mentions | workflow | pg + websocket | S | ★★ | P2 |
| CO3 | Role-based permissions | enterprise | RBAC on channel + scene graph | M | ★★★ | P2 |
| CO4 | Approval queues | QA | Temporal + dashboard | S | ★★★ | P1 |
| CO5 | Audit log | compliance | `agent_runs` + `preference_events` | S | ★★ | P2 |

## 6.7 SDKs / plugin systems

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| SDK1 | TS SDK for scene graph | external integrators | `packages/sdk` with typed builder | M | ★★★★ | P1 |
| SDK2 | Python SDK | glues py services naturally | thin wrapper emitting scene graph JSON | S | ★★★★ | P0 |
| SDK3 | Plugin API for new scenes | ecosystem | `defineScene()` registration helper | S | ★★★ | P1 |
| SDK4 | Plugin API for new effects | ecosystem | `defineEffect()` with t0/t1 adapters | M | ★★★ | P1 |
| SDK5 | Plugin API for new agents | ecosystem | MCP tool registration | S | ★★★ | P1 |
| SDK6 | CLI for local dev (`remvx`) | DX | `remvx render`, `remvx preview` | S | ★★★ | P2 |
| SDK7 | Plugin marketplace | revenue | gumroad-style store + signing | L | ★★★ | P3 |

## 6.8 Templates

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| TPL1 | Per-niche template library | fast start | scene-graph presets per niche | S | ★★★★ | P1 |
| TPL2 | Editable brand kits | consistency | `brandDna` JSON + UI | S | ★★★ | P1 |
| TPL3 | Template parameter UI | non-coders | Zod schema → auto-form | S | ★★★ | P1 |
| TPL4 | Template versioning | safety | `templates` table + semver | S | ★★ | P2 |
| TPL5 | Community template sharing | moat | signed JSON import/export | M | ★★ | P3 |

## 6.9 AI copilots

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| CP1 | Editor copilot ("speed this up", "more B-roll") | creator leverage | chat bound to MCP | M | ★★★★ | P1 |
| CP2 | Art director copilot ("darker mood") | stylistic control | Colorist MCP tool | S | ★★★ | P2 |
| CP3 | Script → full video in 1 click | magic moment | wrapper over all agents | S | ★★★★★ | P0 |
| CP4 | "Why did this flop?" explainer | learning loop | queries retention + critic logs | M | ★★★ | P2 |
| CP5 | "Rewrite for Shorts" copilot | repurposing | pattern transform | S | ★★★★ | P1 |
| CP6 | Translate + dub copilot | reach | multi-lang pipeline (section 04.14) | M | ★★★ | P1 |

## 6.10 Observability / analytics

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| O01 | Cost per video panel | efficiency | Grafana on `remotion_cost_usd_per_video` | S | ★★★★ | P0 |
| O02 | Cache hit ratio panel | optimization | Grafana on cache counters | S | ★★★ | P1 |
| O03 | Agent decision funnel | debuggability | pg `agent_runs` → dashboard | S | ★★★ | P1 |
| O04 | Critic score distribution | quality trends | Grafana histogram | S | ★★★ | P1 |
| O05 | Retention uplift A/B results | learning evidence | `experiments` table → dashboard | S | ★★★★ | P1 |
| O06 | Per-channel style report | creator insight | aggregate priors + outcomes | S | ★★★ | P2 |
| O07 | Fleet heatmap (tier utilization) | capacity planning | Grafana | S | ★★ | P2 |
| O08 | Error taxonomy | reliability | structured error codes + Loki | S | ★★★ | P1 |

## 6.11 Debugging / developer tooling

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| DEV1 | One-click render replay | debug prod | `remvx replay <jobId>` | S | ★★★ | P1 |
| DEV2 | Per-scene timing flamegraph | perf debug | Chrome tracing output | M | ★★★ | P2 |
| DEV3 | Golden-master perceptual tests | regression | SSIM/LPIPS thresholded | M | ★★★★ | P1 |
| DEV4 | Storybook for scenes | component dev | Remotion Studio alt for isolated scenes | S | ★★★ | P1 |
| DEV5 | Fuzz testing for direction-v3 | robustness | Zod fast-check integration | S | ★★ | P2 |
| DEV6 | Deterministic seed harness | reproducibility | seed propagation through agents | S | ★★★ | P1 |
| DEV7 | Frame diff viewer | visual debug | dashboard tool: two videos → pixel diff | M | ★★ | P2 |

## 6.12 Cinematic systems

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| CIN1 | Virtual cinematography library | shot language | shot presets (MS/CU/ECU/WS) as scene graph nodes | M | ★★★★ | P1 |
| CIN2 | Continuity scoring | pro polish | CLIP-based shot adjacency | M | ★★ | P2 |
| CIN3 | Rule of thirds / composition hints | framing | ROI detector + anchor snap | S | ★★★ | P1 |
| CIN4 | Match-cut suggester | editing magic | visual feature matching over adjacent shots | L | ★★ | P3 |
| CIN5 | Look-development presets | style | LUT + tone + grain combos | S | ★★★ | P1 |
| CIN6 | Aspect-aware staging | reframer quality | saliency + Kalman (section 02.11) | M | ★★★★★ | P0 |

## 6.13 Procedural / generative

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| PR1 | Procedural pattern library (patterns → scene graph) | template moat | pattern functions (story arcs) | M | ★★★★ | P1 |
| PR2 | Procedural backgrounds (shader plates) | cheap polish | shader plates in T0 | M | ★★★ | P1 |
| PR3 | Procedural SFX (synthesis) | variety | tone generators per emotion | M | ★★ | P2 |
| PR4 | Procedural typography (character-level animation) | kinetic type | extends `AdvancedKineticText` | M | ★★★ | P1 |
| PR5 | Procedural particles driven by audio | beat-reactive | FFT bins → particle spawn rate | M | ★★★ | P2 |

## 6.14 Design systems

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| DS1 | Token system (colors, typography, spacing) | consistency | `brandDna` → design tokens | S | ★★★ | P1 |
| DS2 | Font library with metrics | legibility | pre-measured font metrics DB | S | ★★ | P1 |
| DS3 | Icon library | reuse | tagged icon set in `components/scenes/IconAnimation.tsx` | S | ★★ | P2 |
| DS4 | Motion tokens (duration, easing) | consistency | easing registry | S | ★★ | P1 |
| DS5 | Accessible color enforcer | WCAG | contrast check in Critic | S | ★★★ | P1 |

## 6.15 Workflow automation

| # | Feature | Why | Sketch | Diff | Impact | Pri |
| - | ------- | --- | ------ | ---- | ------ | --- |
| WF1 | Cron-triggered pipelines | channel ops | already via Temporal schedules | - | ★★★ | P0 |
| WF2 | Trending-topic hot path | faster reaction | trend signal → skip research phase | S | ★★★ | P1 |
| WF3 | Batch regenerate all thumbnails | campaigns | job-per-video workflow | S | ★★ | P2 |
| WF4 | Archive + purge | storage cost | lifecycle on MinIO | S | ★★★ | P1 |
| WF5 | Cross-channel repurpose | leverage | same scene graph → N channels with per-channel brand | M | ★★★★ | P1 |

---

## 6.16 Priority distillation

**P0 (do now)**: R01, R02, R03, R04, R08, R09, A03, I01, I02, I06, I07, I09, I12, I13, I14, I15, I18, I22, C01, C02, CP3, SDK2, O01, CIN6.

These unblock all others. Roughly 3 people for 3–4 months.

**P1 (next)**: tier renderers, reframer, retention predictor, editor UX, SDKs, templates. 3–6 months.

**P2 (consolidation)**: collab, advanced motion, federated learning partial, chaos harness.

**P3 (moonshot)**: regional mesh, edge preview, match-cut, character rigs, full marketplace.

Next: section 07 — how this competes with the incumbents.
