# 02 — The Frame Contract

For every frame the kernel renders, it must be able to **fully reconstruct**
a typed `FrameState` from `(CIR, frame_index, seed_root)` alone — no hidden
state, no closures, no global mutables.

This is the property that makes everything else (caching, sharding, replay,
diff render, RLHF training) possible.

---

## 2.1 The reconstruction principle

```
FrameState(t_us) = pure_fn(CIR, t_us, seed_root)
```

Pure means:

1. No external I/O at evaluation time.
2. No `now()`, no `Math.random()` (only seeded RNGs derived from `seed_root` ⊕ `hash(actor_id) ⊕ t_us / quantum`).
3. Reactive bindings are evaluated against **precomputed** signal buffers when available, or against signals whose tick boundaries are part of the document.
4. All assets are content-hashed and pre-fetched.

This implies: the kernel can render frame 9420 of a 30-minute video without rendering frames 0..9419.

## 2.2 The FrameState type (canonical)

A FrameState is the single value passed to the GPU compositor. Every field is required.

```ts
type FrameState = {
  // ── identity ──────────────────────────────────────────
  doc_hash: Hash;         // sha256:… of the CIR doc
  t_us: bigint;           // microseconds from program origin
  display_frame_index: u32;   // for the active output target
  seed: u64;              // = seed_root ⊕ frame-derived
  output_target_id: string;   // "master" | "youtube_short" | …

  // ── camera ────────────────────────────────────────────
  camera: {
    id: string;
    viewport_px: [u32, u32];
    projection: { kind: "ortho_2d_with_depth_planes" } | { kind: "perspective", fov_rad: f32 };
    transform: Mat4;        // 4×4 column-major
    depth_planes: Array<{ id: string; z: f32; parallax_factor: f32 }>;
    motion_blur: { shutter_angle_deg: f32; samples: u8 };
    focal: { focal_distance: f32; aperture_f: f32; bokeh_kind: string };
    dof_enabled: bool;
  };

  // ── stage state ──────────────────────────────────────
  lights: Array<LightInstance>;       // resolved per frame
  world: { background_color: [f32; 4]; environment_lut_id: string | null };

  // ── layer stack (z-sorted within each plane) ─────────
  layers: Array<LayerInstance>;       // see §2.3 — every visible thing

  // ── audio sample (per-frame slice) ───────────────────
  audio: {
    bus_envelopes: Record<BusId, { rms_db: f32; peak_db: f32; lufs_short: f32 }>;
    voiceover_phoneme: { phoneme: string | null; viseme: string | null; t_offset_us: i64 };
    music_beat_phase: f32;       // 0..1
    sfx_active: Array<{ id: string; envelope_value: f32 }>;
    ducking_gain_db: f32;
    sidechain_state: SidechainState;
  };

  // ── transition state ────────────────────────────────
  transitions: Array<{
    id: string;
    progress: f32;               // 0..1
    kind: TransitionKind;
    params: TransitionParams;
  }>;

  // ── particle state (resolved deterministically) ─────
  particles: Array<ParticleSystemSnapshot>;

  // ── subtitle state ──────────────────────────────────
  caption: {
    active_track_id: string | null;
    visible_words: Array<{ word: string; layout_box: Box2; style: CaptionStyle; emphasis: f32 }>;
    karaoke_progress: f32 | null;
  };

  // ── render directives ────────────────────────────────
  render: {
    color_grade: { lut_id: string; strength: f32; tone_curve: ToneCurveParams };
    grain: { intensity: f32; size: f32; chromatic: f32 };
    bloom: { threshold: f32; intensity: f32 };
    vignette: { strength: f32; smoothness: f32 };
    chromatic_aberration: { offset_px: f32 };
    motion_blur_pass: { enabled: bool };
  };

  // ── semantic state ──────────────────────────────────
  semantics: {
    beat: SemanticBeatRef | null;
    emotion: { valence: f32; arousal: f32; dominance: f32 };
    attention_anchor: { kind: "screen_normalized"; x: f32; y: f32 } | null;
    cognitive_load_estimate: f32;     // 0..1
    retention_score_predicted: f32;   // 0..1
    visual_complexity: f32;           // 0..1
    importance: f32;                  // 0..1 — drives render budget
    eye_focus_target: ScreenBox | null;
  };

  // ── scheduler hints ─────────────────────────────────
  scheduler: {
    tier_preference: "t0" | "t1" | "t2";
    skip_if_unchanged_from_prev_frame: bool; // for static-shot optimization
    priority: u8;                            // 0..255
    deadline_us: bigint | null;
    cache_keys: Array<Hash>;                 // sub-render-graph hashes
  };
};
```

## 2.3 LayerInstance — what every visible thing decomposes into

```ts
type LayerInstance = {
  id: string;
  actor_ref: string;
  plane_id: string;
  visible: bool;
  transform: { translate: [f32,f32,f32]; rotate_quat: [f32,f32,f32,f32]; scale: [f32,f32,f32]; pivot: [f32,f32] };
  bounding_box_screen: Box2;
  opacity: f32;
  blend_mode: BlendMode;          // normal | multiply | screen | add | overlay | …
  mask: MaskRef | null;
  crop: Box2 | null;
  uv_offset: [f32,f32];
  shader_state: {
    program_id: string;
    uniforms: Record<string, ShaderValue>;     // typed, not free-form
    textures: Record<string, TextureBinding>;
    storage_buffers: Record<string, BufferBinding>;
    push_constants: ArrayBuffer;
  };
  motion_vectors: Float32Array;    // for temporal AA / motion-blur post pass
  depth: f32;                      // resolved z within plane
  attention_weight: f32;           // CIE-derived
  importance: f32;                 // CIE-derived
  cache_key: Hash;
};
```

Every layer is **independently renderable**. The compositor walks the layer
list per plane, executes its shader, and composites. There is no React tree
traversal at execution time — that happened at *plan* time.

## 2.4 How FrameState is produced

```mermaid
flowchart LR
  CIR[CIR document] --> P1[plan: lower IR<br/>to render-graph bytecode]
  P1 --> P2[bake: precompute static<br/>tracks & assets]
  P2 --> P3[evaluate(t_us):<br/>walk timeline, resolve tracks,<br/>apply reactive bindings]
  P3 --> P4[FrameState]
  P4 --> P5[GPU exec]
```

Step (3) is what makes "every frame" tractable. It is a pure function over a
small local sub-tree of the IR — not the whole document. Cache hits at this
layer skip GPU work entirely.

## 2.5 The state-resolution algorithm

```text
fn evaluate_frame(cir, t_us, seed_root, output_target):
  fs = FrameState.empty(cir.hash, t_us, seed_root, output_target)

  # 1. Camera resolution (track-driven over time)
  fs.camera = resolve_camera(cir.stage.cameras[output_target.camera_ref], t_us)

  # 2. Active timeline regions
  active_clips = walk_timeline(cir.timeline, t_us)        # returns flat list with parent context

  # 3. Per-clip layer resolution
  for clip in active_clips:
    actor = cir.stage.actors[clip.actor_ref]
    layer = lower_actor_to_layer(actor, clip, t_us, fs.camera, seed_root)
    layer.cache_key = hash_subgraph(actor, clip.params, t_us_quantum, fs.camera.id, output_target.id)
    fs.layers.push(layer)

  # 4. Audio (precomputed envelope buffers + per-frame slice)
  fs.audio = sample_audio_state(cir.score, t_us)

  # 5. Subtitles
  fs.caption = sample_caption_state(cir.score.voiceover, t_us, viewport=fs.camera.viewport_px)

  # 6. Render directives (LUT, grain, bloom, …) — driven by tracks + semantic weighting
  fs.render = resolve_render_directives(cir, t_us)

  # 7. Reactive bindings
  for binding in cir.reactive.bindings:
    src_value = signal_value(binding.source, t_us)
    fs[binding.target.path] = apply_transform(binding.transform, src_value, fs[binding.target.path])

  # 8. Semantics
  fs.semantics = resolve_semantics(cir.semantics, t_us, fs)

  # 9. Scheduler hints
  fs.scheduler.tier_preference = pick_tier(fs.layers)
  fs.scheduler.priority = clamp(round(fs.semantics.importance * 255), 0, 255)
  fs.scheduler.cache_keys = [layer.cache_key for layer in fs.layers]

  return fs
```

`hash_subgraph` is keyed by the **content-hash of the actor + clip params + camera + output target + the time quantum**. Two frames at consecutive microseconds with identical parameters share a cache entry.

## 2.6 Time quantization

Authors emit `t_us` at full microsecond resolution. The kernel quantizes to a
**rendering quantum** to enable cache reuse:

| Tier of motion | Quantum | Notes |
| -------------- | ------- | ----- |
| Static layer | full clip range | cached once across all its frames |
| Slow camera push | 16667 µs (1 frame @ 60fps) | one cache entry per frame |
| Audio-reactive layer | quantum = max(1ms, signal_smoothing_ms) | bound by reactive smoothing |
| Particle system | per-frame | stateful evolution, but seeded |
| Shader with `t` uniform | per-frame | unless shader is annotated `time_invariant` |

## 2.7 What "every frame must specify" really means

The user request asks for explicit specification of every dimension on every frame. The IR satisfies this **without** requiring authors to enumerate frames, because the **track system** is dense:

- **Camera state**: continuous-time bezier track on `camera.transform`.
- **Object positions**: per-actor `transform_track` (constant | linear | bezier | spring | physics).
- **Motion vectors**: derived from `transform_track` derivatives — never authored.
- **Interpolation state**: encoded in `track.bezier`, `track.spring`, `track.cubic_hermite`, `track.step`.
- **Lighting state**: `light.<id>.intensity_track`, `light.<id>.color_track`.
- **Particle state**: deterministic from particle system params + seed + t_us.
- **Transition progress**: `transition.<id>.progress_track`.
- **Subtitle state**: `caption.words[].in_us`, `out_us`, `style_track`.
- **Audio state**: precomputed envelope from `score` document.
- **SFX state**: `score.sfx_cues[].envelope_ref`.
- **Background music state**: `score.music_clips[]` + tempo grid.
- **LUT state**: `track.lut_blend` over time (cross-fade between LUTs).
- **Color grading state**: `track.tone_curve`.
- **Shader state**: per-actor `shader_state.uniforms` + `track.<uniform_name>`.
- **Semantic importance**: `semantics.regions[].importance` interpolates over `range_us`.
- **Attention score**: `semantics.regions[].attention_anchor` resolves to a per-frame anchor with optional Kalman smoothing across regions.
- **Emotional score**: `semantics.regions[].emotion`, interpolated bilinearly across overlapping regions.
- **Retention score**: `signal.model_inference` against `mdl_retention_predict` model — precomputed at plan time, sampled at `tick_us`.
- **Eye-focus target**: `attention_anchor` projected into screen space.
- **Motion intensity**: derivative of camera + actor transforms — kernel computes, not authored.
- **Cognitive load estimation**: weighted sum of layer count + text density + cut frequency in window — kernel computes, but `cognitive_load_budget` is authored as a *constraint*.
- **Viewer engagement prediction**: `signal.model_inference` against `mdl_engagement_predict`.
- **Visual complexity score**: kernel computes from rendered frame's edge entropy + saliency map.
- **Dynamic adaptation metadata**: `outputs.platforms[].reframe_strategy` + per-frame saliency-driven viewport offset.

The author authors **tracks** and **regions**. The kernel materializes
**FrameState** from them. This is the trick that keeps the IR compact and
the semantics complete.

## 2.8 Track grammar (the building blocks)

```jsonc
// Constant
{ "kind": "track.constant", "value": 1.0 }

// Step (snap at boundaries)
{ "kind": "track.step", "keys": [{ "t_us": 0, "value": 0 }, { "t_us": 800000, "value": 1 }] }

// Linear
{ "kind": "track.linear", "keys": [{ "t_us": 0, "value": [0,0] }, { "t_us": 1000000, "value": [100, 0] }] }

// Cubic Bezier (per-key tangents in seconds × value units)
{ "kind": "track.bezier", "keys": [
  { "t_us": 0,       "value": 0.0, "out_handle": [200000,  0.4] },
  { "t_us": 1000000, "value": 1.0, "in_handle":  [-200000, -0.2] }
]}

// Cubic Hermite (alternate parameterization)
{ "kind": "track.cubic_hermite", "keys": [{ "t_us":0,"value":0,"tangent":2.0 }, { "t_us":1000000,"value":1,"tangent":0.0 }] }

// Spring (mass-damper), evaluated by integration; deterministic given dt
{ "kind": "track.spring", "target_track": { "kind":"track.constant","value":1.0 }, "k": 220, "damping": 14, "mass": 1.0, "initial_value": 0.0, "initial_velocity": 0.0 }

// Physics (verlet integration, deterministic seed required)
{ "kind": "track.physics_2d", "system_ref": "phys_text_drop", "binding": "actor.translate" }

// Procedural (parametric noise / simplex / curl etc.)
{ "kind": "track.procedural", "fn": "perlin_3d", "params": { "frequency": 0.4, "amplitude": 12, "seed": 7 } }

// Audio-driven
{ "kind": "track.audio_envelope", "bus": "vo", "smoothing_ms": 30, "domain":[0,0.6], "range":[1.0,1.04] }

// Phoneme-locked (visemes for lip sync, character-by-character text reveal)
{ "kind": "track.phoneme_locked", "voiceover_ref": "score.voiceover", "binding": "viseme" }

// Beat-locked
{ "kind": "track.beat_locked", "music_ref": "mus_doc", "snap": "downbeat", "envelope": { "in_us": 50000, "hold_us": 100000, "out_us": 250000 } }

// Step-by-event (e.g., subtitle word reveal)
{ "kind": "track.text_animated", "words": [/* per-word entries */] }

// Composed (chain of tracks)
{ "kind": "track.compose", "stages": [{ "weight": 0.7, "track": /*…*/ }, { "weight": 0.3, "track": /*…*/ }] }
```

Every track type is closed-form deterministic given its inputs. Springs and
physics tracks integrate from authored initial conditions with fixed `dt`.

## 2.9 Worked example — frame state for t=2_500_000 µs of the §1.16 hook

```jsonc
{
  "doc_hash": "sha256:…",
  "t_us": 2500000,
  "display_frame_index": 75,
  "seed": 0xC0FFEE_C0DE_42,
  "output_target_id": "master",

  "camera": {
    "id": "cam_master",
    "viewport_px": [1920, 1080],
    "projection": { "kind": "ortho_2d_with_depth_planes" },
    "transform": [/* mat4: scale 1.10, translate (-16, 4) */],
    "depth_planes": [{ "id":"bg","z":1.0,"parallax_factor":0.10 },{ "id":"subject","z":0.0,"parallax_factor":0.0 },{ "id":"fg","z":-0.4,"parallax_factor":0.5 }],
    "motion_blur": { "shutter_angle_deg": 180, "samples": 4 },
    "focal": { "focal_distance": 0.0, "aperture_f": 0.0, "bokeh_kind": "none" },
    "dof_enabled": false
  },

  "lights": [],

  "world": { "background_color": [0.02,0.02,0.03,1.0], "environment_lut_id": "lut_archive" },

  "layers": [
    {
      "id": "lyr_archive_plate#1",
      "actor_ref": "act_archive_plate",
      "plane_id": "bg",
      "visible": true,
      "transform": { "translate":[-1.6,0.4,1.0], "rotate_quat":[0,0,0,1], "scale":[1.10,1.10,1], "pivot":[0.5,0.5] },
      "bounding_box_screen": { "x":-32,"y":-12,"w":1984,"h":1104 },
      "opacity": 1.0,
      "blend_mode": "normal",
      "mask": null,
      "crop": null,
      "uv_offset": [0.0,0.0],
      "shader_state": { "program_id":"shd_video_plane","uniforms":{"frame_t_us":2500000},"textures":{"src":{"asset_ref":"ast_pump_archive","frame_us":2500000}},"storage_buffers":{},"push_constants": null },
      "motion_vectors": "<small float32 array>",
      "depth": 1.0,
      "attention_weight": 0.20,
      "importance": 0.4,
      "cache_key": "sha256:…"
    },
    {
      "id": "lyr_hook_text#1",
      "actor_ref": "act_hook_text",
      "plane_id": "subject",
      "visible": true,
      "transform": { "translate":[0,0,0],"rotate_quat":[0,0,0,1],"scale":[1.03,1.03,1],"pivot":[0.5,0.5] },
      "bounding_box_screen": { "x":192,"y":594,"w":1536,"h":324 },
      "opacity": 1.0,
      "blend_mode": "normal",
      "mask": null,
      "crop": null,
      "uv_offset":[0,0],
      "shader_state": {
        "program_id":"shd_kinetic_text",
        "uniforms":{
          "active_word_index": 2,
          "active_word_progress": 0.95,
          "stroke_width_px": 6.0,
          "fill_color":[1,0.94,0.40,1],
          "stroke_color":[0.05,0.05,0.07,1]
        },
        "textures":{ "atlas": { "font_ref":"fnt_inter","glyph_set":"PRICES" } },
        "storage_buffers":{ "word_layouts": { "buffer_ref":"buf_word_layouts_hook","range":[80,160] } },
        "push_constants": null
      },
      "motion_vectors": "<empty>",
      "depth": 0.0,
      "attention_weight": 0.95,
      "importance": 0.95,
      "cache_key": "sha256:…"
    },
    {
      "id": "lyr_grain#1",
      "actor_ref": "act_grain",
      "plane_id": "fg",
      "visible": true,
      "transform": { "translate":[0,0,0],"rotate_quat":[0,0,0,1],"scale":[1,1,1],"pivot":[0.5,0.5] },
      "bounding_box_screen":{ "x":0,"y":0,"w":1920,"h":1080 },
      "opacity": 1.0,
      "blend_mode": "overlay",
      "shader_state":{ "program_id":"shd_grain","uniforms":{ "intensity":0.18,"size":1.0,"seed":42,"t_us":2500000 } },
      "motion_vectors":"<empty>",
      "depth":-0.4,
      "attention_weight": 0.05,
      "importance": 0.1,
      "cache_key": "sha256:…"
    }
  ],

  "audio": {
    "bus_envelopes": {
      "vo":   { "rms_db": -16.4, "peak_db": -8.1, "lufs_short": -14.1 },
      "music":{ "rms_db": -28.2, "peak_db": -16.5, "lufs_short": -22.0 },
      "sfx":  { "rms_db": -24.0, "peak_db": -12.0, "lufs_short": -20.0 }
    },
    "voiceover_phoneme": { "phoneme":"AY1","viseme":"AI","t_offset_us": 12000 },
    "music_beat_phase": 0.50,
    "sfx_active":[{ "id":"sfx_riser","envelope_value":0.62 }],
    "ducking_gain_db": -7.8,
    "sidechain_state": { "envelope_db":-7.8,"gate_open":true }
  },

  "transitions": [],
  "particles": [],

  "caption": {
    "active_track_id": "trk_text",
    "visible_words":[
      { "word":"PRICES","layout_box":{"x":192,"y":594,"w":1536,"h":324},"style":{"font_ref":"fnt_inter","weight":900,"fill":[1,0.94,0.4,1],"stroke":{"width_px":6,"color":[0.05,0.05,0.07,1]}},"emphasis":1.0 }
    ],
    "karaoke_progress": 0.95
  },

  "render": {
    "color_grade": { "lut_id":"lut_archive","strength":0.85,"tone_curve":{ "shadows":-0.05,"midtones":0.02,"highlights":-0.10,"saturation":0.92 } },
    "grain":       { "intensity":0.18,"size":1.0,"chromatic":0.1 },
    "bloom":       { "threshold":0.85,"intensity":1.4 },
    "vignette":    { "strength":0.18,"smoothness":0.6 },
    "chromatic_aberration":{ "offset_px":0.4 },
    "motion_blur_pass":{ "enabled":true }
  },

  "semantics": {
    "beat":{ "name":"hook","range_us":[0,6000000] },
    "emotion":{ "valence":-0.10,"arousal":0.90,"dominance":0.55 },
    "attention_anchor": { "kind":"screen_normalized","x":0.5,"y":0.7 },
    "cognitive_load_estimate":0.42,
    "retention_score_predicted":0.94,
    "visual_complexity":0.36,
    "importance":0.95,
    "eye_focus_target":{ "x":0.50,"y":0.69,"w":0.80,"h":0.30 }
  },

  "scheduler":{
    "tier_preference":"t1",
    "skip_if_unchanged_from_prev_frame": false,
    "priority": 242,
    "deadline_us": null,
    "cache_keys":["sha256:…","sha256:…","sha256:…"]
  }
}
```

This is what one frame *is* in this system: a fully typed value with no
hidden state, completely reproducible from the document.

## 2.10 Implications

- **Streaming preview** is just `evaluate_frame(t_us)` for any t. No need to render frames 0..t.
- **Time-scrub** in an editor is free.
- **Frame-level caching** is correctness-preserving — cache key is `cache_key` per layer.
- **A/B variants** (different hook, different music) only differ in the layers whose `cache_key` changes.
- **Replay** is `compile(CIR) → bytecode; execute(bytecode, seed_root)`.
- **Audit** of any frame: dump FrameState, log to `frame_states` table (sampled).

## 2.11 What the kernel does NOT compute per frame

- It does not re-resolve assets (those are content-hashed and pre-fetched).
- It does not re-bundle React components (T1 reuses `cachedBundle` keyed by content hash).
- It does not re-evaluate ML models per frame (signals are precomputed at their tick rate).
- It does not re-walk the entire IR — it walks the *active region* slice, found via interval-tree lookup over `range_us`.
- It does not allocate (the FrameState struct is a pre-allocated arena per worker).

The kernel's per-frame budget on a documentary scene is on the order of
**100µs of CPU + GPU dispatch** for cache-hot frames; full render only
happens on the cache-cold path.
