# Phase 3 — Premium Features (status)

> Built on top of Phase 1 MVP library and Phase 2 expansion, Phase 3 adds
> premium/advanced capabilities: WebGL shader-based effects, forced-alignment
> word-level captions, data-heavy scenes (timeline/map/code/flowchart), new
> custom transitions, and a centralized 100+ SFX catalog.

## New infrastructure

- `src/components/effects/ShaderCanvas.tsx` — WebGL2 shader host with auto
  uniforms (`u_time`, `u_frame`, `u_resolution`, `u_texel`) and pluggable
  custom uniforms (scalar / vec2 / vec3 / vec4). Supports CSS blend modes so
  shader output composites over the DOM-rendered scene.
- `src/registry/sfxLibrary.ts` — 100 curated SFX IDs across 15 categories
  (whoosh, impact, pop, swoosh, ding, click, ui, riser, drop, glitch, tech,
  cinematic, ambient, transition, notification). `resolveSfx(id)` maps IDs
  to playable URLs using `SFX_BASE_URL` env, per-entry absolute URLs, or
  caller overrides.
- `SegmentRenderer` now accepts SFX library IDs in addition to absolute URLs
  and honours `volume_db` on the cue (defaults come from the library entry).

## Premium effects (shader-based)

| Preset                   | Component     | Notes                                  |
| ------------------------ | ------------- | -------------------------------------- |
| `fx.vhs.subtle|heavy`    | `VHS`         | Noise bands + scanlines + RGB wobble   |
| `fx.crt.classic|arcade`  | `CRT`         | Barrel distort + phosphor + scanlines  |
| `fx.glitch.mild|heavy`   | `Glitch`      | RGB-split bands + pixel static bursts  |
| `fx.lightleaks.warm|magenta` | `LightLeaks` | Travelling warm radial gradients     |
| `fx.scanlines.soft|hard` | `Scanlines`   | Lightweight CSS scanline overlay       |

## Premium scenes

| Preset                                | Component             |
| ------------------------------------- | --------------------- |
| `scene.timeline.horizontal|vertical`  | `TimelineAnimation`   |
| `scene.map.route|pins_only`           | `MapAnimation`        |
| `scene.code.typing_dark_ts|light_py|fast_dark` | `CodeTyping` |
| `scene.flowchart.default`             | `FlowchartAnimation`  |

`CodeTyping` ships with a tiny tokenizer (keywords / strings / numbers /
comments / identifiers) — good enough for JS/TS/Python/Go.  Swap in Shiki for
production-grade highlighting when Remotion chromium perf is not a concern.

## Premium transitions

| Preset                          | Presenter   | Notes                                  |
| ------------------------------- | ----------- | -------------------------------------- |
| `trans.zoompunch.hard|soft`     | `zoomPunch` | Scale-up+blur on outgoing, scale-in on incoming |
| `trans.glitchcut.mild|heavy`    | `glitchCut` | Peak-at-mid RGB-split flicker          |
| `trans.shatter.grid|fine`       | `shatter`   | Outgoing breaks into seeded tiles      |
| `trans.morph.subtle|strong`     | `morph`     | Approximate morph-cut (dissolve+scale+blur) |

`morph` is a fake: true morph-cut needs feature matching across scenes
(ML pre-process).  The approximation reads well for talking-head or similar-
framing cuts.

## Word-level captions

`WordAlignedCaption` overlay consumes `{word, startMs, endMs}[]` — the shape
Whisper produces with `word_timestamps=True` (or MFA / gentle / aeneas
forced alignment). Three styles:

- `karaoke_highlight` — active word glows
- `pop_active` — active word scales up
- `underline_active` — active word underlined

Presets: `ov.wordcap.karaoke_yellow`, `ov.wordcap.karaoke_cyan`,
`ov.wordcap.pop_shorts`, `ov.wordcap.underline_minimal`.

## Totals after Phase 3

Approximate preset counts (see `src/registry/*.ts` for ground truth):

| Category      | Phase 1 | + Phase 2 | + Phase 3 (cumulative) |
| ------------- | ------- | --------- | ---------------------- |
| Scenes        | ~19     | ~37       | **~45**                |
| Transitions   | ~15     | ~28       | **~36**                |
| Effects       | ~10     | ~29       | **~39**                |
| Overlays      | ~9      | ~20       | **~24**                |
| Animations    | ~12     | ~22       | ~22 (unchanged)        |
| **SFX IDs**   | 0       | 0         | **100**                |

## Phase 3 pending (future work)

- True post-process shader pass (render scene → OffthreadVideo → shader) for
  effects that need to sample scene pixels (displacement, true RGB-split,
  chroma key). Requires Remotion v4 `<OffthreadVideo>` pipelining.
- Real LUT sampling in the shader (3D LUT texture upload) — current LUTs are
  CSS filter approximations.
- Real morph-cut via feature matching (AI pre-process generating warp mesh).
- Shiki-based syntax highlighting in `CodeTyping` once CHromium perf is
  validated with the heavier bundle.
- Populate the SFX bucket with the 100 curated files and verify loudness
  targets match `defaultDb` in the library.
