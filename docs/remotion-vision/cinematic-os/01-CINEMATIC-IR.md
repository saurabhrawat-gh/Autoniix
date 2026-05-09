# 01 — The Cinematic IR (CIR)

The single contract between the Cinematic Intelligence Engine (CIE) and the
Cinematic OS kernel. **Nothing else** crosses that boundary.

> CIR is to cinematic compilers what LLVM IR is to C compilers: a typed,
> versioned, multi-dialect intermediate representation designed for *machine*
> authoring and *machine* analysis. Humans tolerate it; models love it.

---

## 1.1 Design tenets

1. **Typed everywhere.** Every node carries a `kind`, a `version`, a `hash`, and a typed schema URI.
2. **Microsecond grid.** All temporal fields are `u64` microseconds. fps is encoded only at the *display* layer.
3. **Content-addressed assets.** Every asset is `{sha256, mime, transform_descriptor}` — never a URL at execution time.
4. **Hermetic dependencies.** Models, fonts, shaders, LUTs, SFX — all referenced by sha256 and pinned bytecode where possible.
5. **No string magic.** No expression strings (`"opacity * 2 + sin(t)"`). All math is structured tree.
6. **Hashes propagate.** Every node has a sha256 over its canonicalized form. Changing a property at depth invalidates exactly the parents that need re-rendering.
7. **Multi-dialect.** A single IR document can carry overlapping dialects: `cinematic.core`, `cinematic.audio`, `cinematic.shader`, `cinematic.semantic`, `cinematic.platform`, `cinematic.reactive`.
8. **Bytecode lowering.** CIR → `RenderGraphBytecode` (file `04-RENDER-GRAPH-AND-GPU.md`). The kernel never executes JSON; it executes bytecode.

## 1.2 Top-level document

```jsonc
{
  "$schema": "https://yt-engine.dev/cir/1.0.0/document.json",
  "kind": "cir.document",
  "version": "1.0.0",
  "id": "doc-2031df87",
  "hash": "sha256:…",
  "created_at_us": 1715212345678901,

  "metadata": { /* §1.3 */ },
  "policy":   { /* §1.4 */ },
  "registry": { /* §1.5 — content-addressed asset + shader + model index */ },
  "stage":    { /* §1.6 — virtual stage: cameras, lights, materials, world */ },
  "score":    { /* §1.7 — audio document */ },
  "timeline": { /* §1.8 — root timeline node, see 03-TIMELINE */ },
  "semantics":{ /* §1.9 — per-region annotations: emotion, attention, retention */ },
  "outputs":  { /* §1.10 — master + per-platform render targets */ },
  "reactive": { /* §1.11 — runtime-injected signals + their bindings */ },
  "diagnostics": { /* §1.12 — emitter trace, optional */ }
}
```

## 1.3 metadata

```jsonc
{
  "title": "The 1973 oil crisis",
  "channel_id": "ch-history-explainer",
  "niche": "documentary.history",
  "language": "en-US",
  "intended_total_us": 484000000,
  "fps_master": 30,
  "color_space": { "transfer": "bt709", "primaries": "bt709", "range": "limited" },
  "loudness_target_lufs": -14.0,
  "loudness_max_tp_db": -1.0,
  "reproducibility": { "seed_root": 0xC0FFEE, "rng": "xoshiro256pp" },
  "emitter": { "model": "claude-opus-4.5", "model_hash": "sha256:…", "trace_id": "…" }
}
```

## 1.4 policy

```jsonc
{
  "monetization_safe": true,
  "platform_targets": ["youtube_long", "youtube_short", "tiktok", "instagram_reel"],
  "content_rating": "general",
  "consent": { "voice_cloning": true, "face_likeness": false },
  "cost_ceiling_usd": 0.40,
  "wall_deadline_s": 600,
  "fallback_policy": "graceful_degrade"
}
```

`fallback_policy` ∈ `{ strict, graceful_degrade, fail_fast }` — the kernel reads this when a tier is unavailable.

## 1.5 registry — content-addressed everything

```jsonc
{
  "assets": {
    "ast_oilrig_dusk": {
      "kind": "asset.video",
      "sha256": "sha256:8b0f…",
      "mime": "video/mp4",
      "duration_us": 12000000,
      "resolution": [3840, 2160],
      "framerate": 24000/1001,
      "cdn_url": "https://cdn/.../8b0f…",
      "license": { "kind": "envato_pro", "rights": ["monetized","derivative"], "expires_at_us": null },
      "phash": "phash:9c…"
    },
    "ast_archive_1973": { "kind": "asset.video", "sha256": "sha256:1f3a…", "transform": { "deinterlace": "yadif", "denoise_strength": 0.3 }, "_": "…" }
  },
  "fonts": {
    "fnt_inter_var": { "sha256": "sha256:…", "axes": ["wght","wdth","ital"], "subset": "latin+ext" }
  },
  "shaders": {
    "shd_kinetic_text_v3": { "lang": "wgsl", "sha256": "sha256:…", "entry_points": ["vs_main","fs_main"], "bindings": [/*…*/] },
    "shd_lut_grade":       { "lang": "wgsl", "sha256": "sha256:…" }
  },
  "luts": {
    "lut_warm_filmic_v2": { "format": "cube33", "sha256": "sha256:…", "domain": "log_to_lin_bt709" }
  },
  "models": {
    "mdl_phoneme_align":  { "kind": "phoneme", "sha256": "sha256:…", "version": "wav2vec2-960h" },
    "mdl_saliency":       { "kind": "vision", "sha256": "sha256:…", "version": "sam2-base" }
  },
  "voices": {
    "vox_anchor_a":       { "engine": "fish_audio", "voice_id": "v_…", "sha256_signature": "sha256:…" }
  },
  "music": {
    "mus_documentary_bed": { "sha256": "sha256:…", "duration_us": 600000000, "bpm": 84.0, "downbeat_grid_us": [/*…*/] }
  },
  "sfx": {
    "sfx_riser_long":      { "sha256": "sha256:…", "duration_us": 4200000 }
  }
}
```

Two rules:

1. **Anything referenced anywhere else in the document MUST exist in `registry`.** Compile fails otherwise.
2. **Hashes are mandatory.** No URL-only references at the IR level. The fetcher resolves them at *plan* time, not *frame* time.

## 1.6 stage — the virtual cinematic environment

```jsonc
{
  "world": { "background_color": [0.02, 0.02, 0.03, 1.0], "environment_lut_ref": "lut_warm_filmic_v2" },
  "cameras": {
    "cam_master": {
      "kind": "camera.cinematic",
      "projection": "ortho_2d_with_depth_planes",
      "viewport_master_px": [1920, 1080],
      "depth_planes": [
        { "id": "bg",      "z": 1.0, "parallax_factor": 0.10 },
        { "id": "midbg",   "z": 0.6, "parallax_factor": 0.30 },
        { "id": "subject", "z": 0.0, "parallax_factor": 0.00 },
        { "id": "fg",      "z": -0.4, "parallax_factor": 0.50 }
      ]
    }
  },
  "lights": {
    "key": { "kind": "light.directional", "color": [1,0.95,0.85], "intensity": 1.0, "direction": [0.3,-0.6,-0.7] },
    "fill": { "kind": "light.ambient",   "color": [0.7,0.8,1.0], "intensity": 0.25 }
  },
  "materials": {
    "mat_paper_grain":  { "shader_ref": "shd_film_grain", "params": { "intensity": 0.18, "seed": 42 } },
    "mat_glow_warm":    { "shader_ref": "shd_bloom",      "params": { "threshold": 0.85, "intensity": 1.4 } }
  },
  "actors": {
    "act_title_card_intro": { "kind": "actor.kinetic_text", "shader_ref": "shd_kinetic_text_v3", "default_material_ref": "mat_glow_warm" },
    "act_oilrig_clip":      { "kind": "actor.video_plane",  "asset_ref": "ast_oilrig_dusk" }
  }
}
```

`stage` is the **declarative scene database**. Timelines reference `actors`, never inline them. This is what lets two timelines share a kinetic-text actor with different per-instance parameter tracks.

## 1.7 score — audio document (full detail in §09)

```jsonc
{
  "tempo_grid_us": [/* downbeat boundaries derived from `mus_documentary_bed` */],
  "buses": {
    "vo":    { "level_db": 0.0, "limiter": { "ceiling_db": -1.0, "release_ms": 50 } },
    "music": { "level_db": -8.0, "ducking": { "source_bus": "vo", "ratio": 4.0, "threshold_db": -32, "attack_ms": 8, "release_ms": 220 } },
    "sfx":   { "level_db": -3.0 },
    "amb":   { "level_db": -18.0 }
  },
  "voiceover": {
    "asset_ref": null,
    "synth": { "voice_ref": "vox_anchor_a", "ssml_ref": "ssml_block_main" },
    "phoneme_alignment_ref": "mdl_phoneme_align"
  },
  "music_clips": [{ "asset_ref": "mus_documentary_bed", "in_us": 0, "out_us": 484000000, "fade_in_us": 800000, "fade_out_us": 1200000 }],
  "sfx_cues": [
    { "asset_ref": "sfx_riser_long", "at_us": 480000, "bus": "sfx", "envelope_ref": "env_riser_default" }
  ]
}
```

## 1.8 timeline — root node

Pointer into the timeline-tree dialect (full spec: `03-TIMELINE-AND-SCENE-GRAPH.md`):

```jsonc
{
  "kind": "timeline.sequence",
  "id": "tl_root",
  "duration_us": 484000000,
  "tracks": [ /* nested timeline / track nodes */ ],
  "semantic_tags": ["doc_arc:act1","doc_arc:act2","doc_arc:act3"],
  "hash": "sha256:…"
}
```

## 1.9 semantics — typed annotations layered over time-space

```jsonc
{
  "regions": [
    {
      "kind": "semantic.beat",
      "name": "hook",
      "range_us": [0, 4000000],
      "emotion": { "valence": 0.20, "arousal": 0.85, "dominance": 0.60 },
      "retention_target": 0.92,
      "attention_anchor": { "kind": "screen_normalized", "x": 0.50, "y": 0.42 },
      "cognitive_load_budget": 0.65
    },
    {
      "kind": "semantic.beat",
      "name": "tension_rise",
      "range_us": [4000000, 38000000],
      "emotion": { "valence": -0.15, "arousal": 0.55, "dominance": 0.40 },
      "retention_target": 0.78
    },
    {
      "kind": "semantic.pattern_interrupt",
      "at_us": 35000000,
      "intensity": 0.7,
      "intent": "prevent_4_to_5min_dropoff"
    },
    {
      "kind": "semantic.attention_lock",
      "range_us": [240000000, 246000000],
      "target_actor": "act_title_card_chapter2",
      "guidance": ["zoom_punch","caption_flash","sfx_stinger"]
    }
  ]
}
```

These annotations don't render anything by themselves. They are read by:

- The **CIE** during authoring (the editor agent uses them to plan cuts).
- The **kernel** during planning (scheduler uses `cognitive_load_budget` + `retention_target` to allocate render budget).
- The **critic** during evaluation (compares achieved retention curve to target).

## 1.10 outputs — render targets

```jsonc
{
  "master": {
    "kind": "output.master",
    "viewport_px": [1920, 1080],
    "fps_display": 30,
    "codec": "h264",
    "encoder_hint": "auto",
    "crf_or_bitrate": { "kind": "crf", "value": 18 },
    "color_space": { "transfer": "bt709", "primaries": "bt709" }
  },
  "ladders": [
    { "kind": "output.ladder", "viewport_px": [1280, 720], "bitrate_kbps": 3500 },
    { "kind": "output.ladder", "viewport_px": [854, 480],  "bitrate_kbps": 1200 }
  ],
  "platforms": [
    {
      "kind": "output.platform",
      "id": "youtube_short",
      "viewport_px": [1080, 1920],
      "duration_us": 60000000,
      "reframe_strategy": { "kind": "saliency", "model_ref": "mdl_saliency", "kalman_q": 0.01 },
      "selector": { "kind": "story_arc.shorts_excerpt", "params": { "from_pattern": "data_reveal" } }
    },
    {
      "kind": "output.platform",
      "id": "instagram_square",
      "viewport_px": [1080, 1080],
      "reframe_strategy": { "kind": "static_safe_zone", "anchor": [0.5, 0.5] }
    }
  ],
  "stems": { "video_only": true, "mixed_audio": true, "per_bus_stems": ["vo","music","sfx"] },
  "thumbnail": { "still_at_us": 1500000, "alts_at_us": [12000000, 240000000] }
}
```

A **single** CIR document produces N outputs deterministically. Reframer + ladder fan-out is built into the IR; there's no "second render".

## 1.11 reactive — runtime signals and bindings

```jsonc
{
  "signals": {
    "sig_audio_rms_vo":     { "kind": "signal.audio_envelope", "bus": "vo", "smoothing_ms": 30 },
    "sig_retention_predict":{ "kind": "signal.model_inference", "model_ref": "mdl_retention_predict", "tick_us": 100000 },
    "sig_critic_score":     { "kind": "signal.external", "tick_us": 1000000 }
  },
  "bindings": [
    {
      "target": { "actor": "act_subtitle_track", "param": "scale" },
      "source": "sig_audio_rms_vo",
      "transform": { "kind": "linear", "domain": [0.0, 0.6], "range": [0.95, 1.05] }
    }
  ]
}
```

Reactive bindings turn the kernel into a *dataflow* engine for the parts that need it (audio-reactive captions, retention-aware pacing) while keeping everything else fully precomputed and cacheable.

## 1.12 diagnostics — optional emitter trace

```jsonc
{
  "decisions": [
    { "agent": "director",     "version": "1.4.0", "rule": "hook_promote", "input_hash": "…", "output_hash": "…" },
    { "agent": "cinematographer","version": "0.9.2", "rule": "push_on_beat", "params": { "beat_index": 4 } }
  ],
  "model_calls": [
    { "model": "claude-opus-4.5", "tokens_in": 12000, "tokens_out": 3400, "cost_usd": 0.18 }
  ]
}
```

Diagnostics never affect rendering — they are for replay, audit, and bandit training.

## 1.13 Dialects

CIR is multi-dialect. The kernel only requires `cinematic.core`. Other dialects are optional but typed-checked when present:

| Dialect | Lives under | Purpose |
| ------- | ----------- | ------- |
| `cinematic.core` | `timeline`, `stage`, `outputs`, `metadata` | Required. What MUST render. |
| `cinematic.audio` | `score`, `score.buses`, `score.voiceover` | Audio graph + sync. |
| `cinematic.shader` | `registry.shaders`, `stage.materials` | GPU programs. |
| `cinematic.semantic` | `semantics` | Emotion/attention/retention typing. |
| `cinematic.platform` | `outputs.platforms` | Reframer + per-platform overrides. |
| `cinematic.reactive` | `reactive` | Live signals → dataflow bindings. |
| `cinematic.story` | `metadata.story_pattern`, `semantic.beat` | Pattern templates: `doc_arc`, `data_reveal`, etc. |

A document declares which dialects it uses. Compile fails closed on unknown dialects unless `policy.allow_unknown_dialects = true`.

## 1.14 Hashing & equivalence

Every node carries `hash: "sha256:<hex>"` computed over a canonicalized form:

1. Sort object keys lexicographically.
2. Strip `undefined` and `null` (these are equivalent to absent).
3. Strip `hash` field itself.
4. Stringify numbers per JSON IEEE-754 short representation.
5. SHA256 of UTF-8.

**Equivalence theorem (asserted):** two CIR documents with the same root hash, same `metadata.reproducibility`, and the same hardware profile produce **byte-identical bitstreams**.

This is the property the kernel and the cache rely on. Violations (e.g. nondeterministic shader output) are CI bugs, not features.

## 1.15 JSON Schema (excerpt of the strict definition)

```jsonc
{
  "$id": "https://yt-engine.dev/cir/1.0.0/document.json",
  "type": "object",
  "required": ["kind", "version", "id", "hash", "metadata", "registry", "stage", "timeline", "outputs"],
  "properties": {
    "kind":    { "const": "cir.document" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "id":      { "type": "string", "minLength": 4 },
    "hash":    { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" },
    "metadata":{ "$ref": "#/definitions/metadata" },
    "registry":{ "$ref": "#/definitions/registry" },
    "stage":   { "$ref": "#/definitions/stage" },
    "score":   { "$ref": "#/definitions/score" },
    "timeline":{ "$ref": "#/definitions/timelineNode" },
    "semantics": { "$ref": "#/definitions/semantics" },
    "outputs": { "$ref": "#/definitions/outputs" },
    "reactive":{ "$ref": "#/definitions/reactive" }
  },
  "additionalProperties": false
}
```

Schemas are versioned. `1.0.0`, `1.1.0`, `2.0.0` follow semver: minor bumps add fields, major bumps may break compat (with a migration in `cir/migrations/`).

## 1.16 Worked example — a 6-second hook

```jsonc
{
  "kind": "cir.document",
  "version": "1.0.0",
  "id": "doc-hook6s",
  "hash": "sha256:…",
  "created_at_us": 1715212345678901,

  "metadata": {
    "title": "Why oil prices changed everything",
    "channel_id": "ch-finance-history",
    "niche": "documentary.history",
    "language": "en-US",
    "intended_total_us": 6000000,
    "fps_master": 30,
    "color_space": { "transfer": "bt709", "primaries": "bt709", "range": "limited" },
    "loudness_target_lufs": -14.0,
    "reproducibility": { "seed_root": 7777, "rng": "xoshiro256pp" }
  },

  "policy": { "monetization_safe": true, "platform_targets": ["youtube_long","youtube_short"], "cost_ceiling_usd": 0.05 },

  "registry": {
    "assets": {
      "ast_pump_archive": { "kind":"asset.video", "sha256":"sha256:8b…","mime":"video/mp4","duration_us":4200000,"resolution":[1920,1080],"framerate":30,"license":{"kind":"public_domain","rights":["monetized","derivative"]} }
    },
    "fonts":   { "fnt_inter": { "sha256":"sha256:…","subset":"latin" } },
    "shaders": { "shd_kinetic_text": { "lang":"wgsl","sha256":"sha256:…" }, "shd_grain": { "lang":"wgsl","sha256":"sha256:…" } },
    "luts":    { "lut_archive": { "format":"cube33","sha256":"sha256:…","domain":"log_to_lin_bt709" } },
    "voices":  { "vox_a": { "engine":"fish_audio","voice_id":"v_42","sha256_signature":"sha256:…" } },
    "music":   { "mus_doc": { "sha256":"sha256:…","duration_us":600000000,"bpm":84,"downbeat_grid_us":[0,714286,1428571,2142857,2857143,3571429,4285714,5000000,5714286] } },
    "sfx":     { "sfx_riser": { "sha256":"sha256:…","duration_us":4000000 } }
  },

  "stage": {
    "world": { "background_color": [0.02,0.02,0.03,1.0], "environment_lut_ref": "lut_archive" },
    "cameras": { "cam_master": { "kind":"camera.cinematic","viewport_master_px":[1920,1080],"depth_planes":[{"id":"bg","z":1.0,"parallax_factor":0.10},{"id":"subject","z":0.0,"parallax_factor":0.0}] } },
    "actors": {
      "act_archive_plate": { "kind":"actor.video_plane","asset_ref":"ast_pump_archive","plane":"bg" },
      "act_hook_text":     { "kind":"actor.kinetic_text","shader_ref":"shd_kinetic_text","plane":"subject","layout":{"box":[0.10,0.55,0.90,0.85],"align":["center","center"]} },
      "act_grain":         { "kind":"actor.fullscreen_shader","shader_ref":"shd_grain","plane":"fg" }
    }
  },

  "score": {
    "tempo_grid_us": [0,714286,1428571,2142857,2857143,3571429,4285714,5000000,5714286],
    "buses": {
      "vo":    { "level_db": 0.0,  "limiter": { "ceiling_db": -1.0, "release_ms": 50 } },
      "music": { "level_db": -8.0, "ducking": { "source_bus":"vo","ratio":4.0,"threshold_db":-32,"attack_ms":8,"release_ms":220 } },
      "sfx":   { "level_db": -3.0 }
    },
    "voiceover": { "synth": { "voice_ref":"vox_a", "ssml_ref":"ssml_hook" }, "phoneme_alignment_ref": "mdl_phoneme_align" },
    "music_clips":[{"asset_ref":"mus_doc","in_us":0,"out_us":6000000,"fade_in_us":300000,"fade_out_us":600000}],
    "sfx_cues":  [{"asset_ref":"sfx_riser","at_us":0,"bus":"sfx","envelope_ref":"env_riser_default"}]
  },

  "timeline": {
    "kind":"timeline.sequence","id":"tl_root","duration_us":6000000,
    "tracks":[
      {
        "kind":"timeline.track","id":"trk_video","clips":[
          { "kind":"clip.actor","actor_ref":"act_archive_plate","range_us":[0,6000000],"params": {
              "transform_track": { "kind":"track.bezier","keys":[
                { "t_us": 0,       "value": { "scale": 1.05, "translate":[0,0]}, "out_handle":[1000000,0.05] },
                { "t_us": 6000000, "value": { "scale": 1.20, "translate":[-40,10]}, "in_handle":[-1000000,-0.05] }
              ]},
              "opacity_track":  { "kind":"track.constant","value": 1.0 },
              "lut_track":      { "kind":"track.constant","value": "lut_archive" }
          }}
        ]
      },
      {
        "kind":"timeline.track","id":"trk_text","clips":[
          { "kind":"clip.actor","actor_ref":"act_hook_text","range_us":[400000,5800000],"params": {
              "text_track": { "kind":"track.text_animated","words":[
                { "text":"WHY",        "in_us":400000,  "out_us":900000,  "anim":"snap_in" },
                { "text":"OIL",        "in_us":950000,  "out_us":1500000, "anim":"snap_in" },
                { "text":"PRICES",     "in_us":1550000, "out_us":2300000, "anim":"snap_in" },
                { "text":"CHANGED",    "in_us":2350000, "out_us":3300000, "anim":"snap_in" },
                { "text":"EVERYTHING", "in_us":3350000, "out_us":5800000, "anim":"slow_zoom" }
              ]}
          }}
        ]
      },
      {
        "kind":"timeline.track","id":"trk_grain","clips":[
          { "kind":"clip.actor","actor_ref":"act_grain","range_us":[0,6000000],"params":{ "intensity_track": { "kind":"track.constant","value":0.18 } } }
        ]
      }
    ]
  },

  "semantics": {
    "regions": [
      { "kind":"semantic.beat","name":"hook","range_us":[0,6000000],"emotion":{"valence":-0.1,"arousal":0.9,"dominance":0.55},"retention_target":0.95,"attention_anchor":{"kind":"screen_normalized","x":0.5,"y":0.7},"cognitive_load_budget":0.6 },
      { "kind":"semantic.attention_lock","range_us":[400000,5800000],"target_actor":"act_hook_text","guidance":["caption_progressive_reveal"] }
    ]
  },

  "outputs": {
    "master":   { "kind":"output.master","viewport_px":[1920,1080],"fps_display":30,"codec":"h264","crf_or_bitrate":{"kind":"crf","value":18},"color_space":{"transfer":"bt709","primaries":"bt709"} },
    "ladders":  [{ "kind":"output.ladder","viewport_px":[1280,720],"bitrate_kbps":3500 }],
    "platforms":[{ "kind":"output.platform","id":"youtube_short","viewport_px":[1080,1920],"duration_us":6000000,"reframe_strategy":{"kind":"saliency","model_ref":"mdl_saliency","kalman_q":0.01} }],
    "stems":    { "video_only": true, "mixed_audio": true, "per_bus_stems":["vo","music","sfx"] }
  },

  "reactive": { "signals": { "sig_vo_rms": { "kind":"signal.audio_envelope","bus":"vo","smoothing_ms":30 } },
                "bindings":[{ "target":{"actor":"act_hook_text","param":"scale"},"source":"sig_vo_rms","transform":{"kind":"linear","domain":[0,0.6],"range":[1.0,1.04]}}] }
}
```

This 6-second hook is hand-written here for documentation only. In production the **Cinematic Intelligence Engine** emits documents like this — typically several thousand lines for a 10-minute video — and they are *machine outputs*, not human writing.

## 1.17 What the IR explicitly forbids

These are *bugs* if they appear:

- Bare URLs in any non-registry field.
- `expression` strings (e.g., `"opacity * 2"`).
- Time fields in milliseconds, frames, or `Date` strings (only `t_us: u64`).
- Inline asset bytes (base64).
- Implicit defaults that aren't written in the schema.
- Non-deterministic constructs (`Math.random()`, wall-clock time).
- Anonymous shaders / fonts / models.

Each of these is rejected by the validator at `cir.validate()`.

## 1.18 What lives in the next files

- `02-FRAME-CONTRACT.md` — the per-frame state vector that the kernel computes from this IR.
- `03-TIMELINE-AND-SCENE-GRAPH.md` — full grammar for `timeline.*` nodes, including parallel/branching/conditional/reactive.
- `04-RENDER-GRAPH-AND-GPU.md` — how CIR lowers to a render-graph DAG and runs on GPU.
- `05-CINEMATIC-INTELLIGENCE-ENGINE.md` — how the upstream AI authors CIR.
- `06-EXECUTION-LIFECYCLE-AND-MOONSHOTS.md` — end-to-end lifecycle.
