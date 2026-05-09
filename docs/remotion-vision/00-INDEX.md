# Remotion Vision — Index

A multi-file strategic and architectural treatise that audits the existing `services/remotion` pipeline in this `yt-automation-n8n` stack and proposes its evolution into an AI-native autonomous cinematic rendering platform.

## Thesis

Remotion is the most leverageable open-source video primitive: deterministic, React-composable, schema-driven, headless. It is not today a video **engine** in the sense Adobe / DaVinci / Runway / Sora are. The gap is not features — it is **architecture, intelligence, and orchestration**. This set keeps Remotion at the rendering core but adds the missing scene-graph IR, hybrid GPU compositor, agentic director/editor/critic topology, multi-format output engine, and distributed render mesh.

## Reading order

| # | File | Audience |
| - | ---- | -------- |
| 1 | `01-CURRENT-STATE-AUDIT.md` | Eng, ML, leadership |
| 2 | `02-FUTURE-ENGINE-ARCHITECTURE.md` | Eng, infra |
| 3 | `03-INTELLIGENCE-LAYER.md` | ML, agents |
| 4 | `04-FACELESS-VIDEO-ENGINE.md` | Product, content |
| 5 | `05-PERFORMANCE-AND-SCALE.md` | Infra, SRE |
| 6 | `06-FEATURE-CATALOG.md` | PM, eng |
| 7 | `07-COMPETITIVE-ROADMAP.md` | Leadership |
| 8 | `08-IMPLEMENTATION-PLAN.md` | Eng leads, founders |

10 minutes: this + section 8. 30: add 1, 2, 3. 2 hours: all.

## Grounding anchors

Every "current state" claim is anchored to a real file. Every "future" claim points to a concrete extension surface, not a rewrite.

- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/api/server.ts:1-133`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/api/queue.ts:1-35`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/worker/renderer.ts:1-225`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/Root.tsx:1-86`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/registry/` — animations, transitions, effects, overlays, scenes, sfxLibrary, lutLibrary, grainLibrary
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/components/` — 23 scenes / 12 animations / 22 effects / 13 overlays / 4 audio / 3 branding
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/services/assetResolver.ts:1-250`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/schemas/directionV3.ts`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/utils/compositionValidator.ts`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/src/utils/postRenderQc.ts`

Stack-level:

- `@/home/saurabh/Desktop/YouTube/youtube-automation/docker-compose.yml` — `remotion-api` (4000) + `remotion-worker` (4G) on shared Redis + MinIO
- `@/home/saurabh/Desktop/YouTube/youtube-automation/src/temporal_workflows/video_production.py` — Phase 5 Assembly, Phase 5B Editor consume Remotion
- `@/home/saurabh/Desktop/YouTube/youtube-automation/src/services/script/direction_engine.py` — emits direction-v3
- `@/home/saurabh/Desktop/YouTube/youtube-automation/src/services/assembly/render_predictor.py` — predicts render complexity / duration

Existing roadmap docs this set complements (not replaces):

- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/FUTURE_ROADMAP.md`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/IMPLEMENTED_FEATURES.md`
- `@/home/saurabh/Desktop/YouTube/youtube-automation/services/remotion/PENDING_TASKS.md`

## Glossary

| Term | Meaning |
| ---- | ------- |
| **Composition** | Remotion `<Composition>` in `Root.tsx`: `MainVideo`, `ShortFormVideo`, `ThumbnailComp`. |
| **Direction v3** | JSON contract `DirectionV3` in `src/schemas/directionV3.ts`. Source of truth for what to render. |
| **Segment** | `direction.segments[i]` — timed slice with `duration_ms`, voiceover, asset, scene type. |
| **Scene Graph IR** | *Proposed.* Typed node graph (clip / track / effect / transition / audio) lowered from direction-v3. |
| **Tier 0 / 1 / 2** | *Proposed.* WebGPU compositor / Chromium / ffmpeg-direct renderers with a per-scene capability router. |
| **Render shard** | Frame-range subset of a render job, parallel-dispatched, re-assembled by ffmpeg `concat`. |
| **Critic agent** | Vision-LLM scorer grading frames against a rubric. |
| **Repair agent** | Mutates scene graph and re-renders only critic-flagged shards. |
| **Reframer** | Maps a 16:9 master scene graph onto 9:16 / 1:1 / 4:5 via saliency. |
| **MCP server** | Model-Context-Protocol surface exposing Remotion as tools. |
| **Diff render cache** | Frame cache keyed by sub-scene-graph hash. |

## What this doc set is NOT

- Not a tutorial. Not a feature wishlist without anchors. Not a rewrite proposal. Not vendor-neutral — it is anchored to this repo.
