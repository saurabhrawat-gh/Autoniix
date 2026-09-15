# D. Direction Format v3 — JSON Schema

> The JSON contract between the AI director (upstream) and the Remotion renderer (this repo). Designed to reference **preset IDs** rather than inline component props, enabling the registry pattern from doc C.

---

## 1. Top-level shape

```jsonc
{
  "version": "3.0",
  "meta": {
    "video_id": "vid_abc123",
    "channel_id": "chan_xyz",
    "title": "Why You Shiver When You Pee",
    "duration_target_seconds": 600,
    "aspect": "16:9", // or "9:16" | "1:1"
    "fps": 30,
    "resolution": { "width": 1920, "height": 1080 },
  },
  "template": "hybrid-kinetic", // one of 21 template IDs
  "theme": {
    "primary_color": "#FF3B30",
    "accent_color": "#FFD60A",
    "background_color": "#0A0A0A",
    "text_color": "#FFFFFF",
    "fonts": { "heading": "Montserrat", "body": "Inter" },
  },
  "grade_preset": "fx.grade.cinematic_teal_orange",
  "global_effects": ["fx.grain.film_35mm", "fx.vignette.soft"],
  "global_overlays": [
    { "preset": "ov.caption.word_highlight_yellow" },
    { "preset": "ov.logobug.tr_small", "overrides": { "src": "https://cdn/logo.png" } },
  ],
  "audio": {
    "voiceover_url": "https://cdn/.../vo.mp3",
    "voiceover_srt_url": "https://cdn/.../vo.srt",
    "music_url": "https://cdn/.../bgm.mp3",
    "music_volume_db": -18,
    "ducking": { "enabled": true, "threshold_db": -30, "attack_ms": 100, "release_ms": 400 },
    "loudness_target_lufs": -14,
  },
  "branding": {
    "intro_preset": "branding.intro.logo_reveal_neon",
    "outro_preset": "branding.outro.endscreen_2vid_1sub",
    "watermark": { "preset": "ov.logobug.tr_small", "src": "https://cdn/logo.png" },
  },
  "segments": [/* ordered list, see §2 */],
  "thumbnail": {/* see §3 */},
}
```

---

## 2. Segment shape

```jsonc
{
  "id": "seg_01",
  "start_ms": 0,
  "duration_ms": 5000,
  "scene_preset": "scene.hook.question_flash",
  "scene_overrides": {
    "text": "Why do you shiver when you pee?",
    "subtitle": "You're not weird. It's physics.",
  },
  "animations_in": [{ "preset": "anim.in.scale_punch", "target": "headline" }],
  "animations_out": [{ "preset": "anim.out.fade" }],
  "effects": ["fx.chromatic.subtle"],
  "overlays": [{ "preset": "ov.caption.word_highlight_yellow" }],
  "sfx": [
    { "preset": "sfx.whoosh.fast", "at_ms": 0 },
    { "preset": "sfx.impact.heavy", "at_ms": 300 },
  ],
  "transition_out": {
    "preset": "trans.zoom.punch_hard",
    "overrides": { "durationInFrames": 6 },
  },
}
```

### Rules

- Exactly one `scene_preset` per segment.
- `transition_out` is the transition **into the next** segment; last segment's is ignored.
- `overrides` shallow-merge onto preset `defaultProps`.
- All timing in **ms** in JSON; renderer converts to frames using `meta.fps`.
- `animations_in/out` can target sub-elements of scenes via `target` (scene-specific slot names).

---

## 3. Thumbnail shape

```jsonc
"thumbnail": {
  "composition": "ThumbnailComp",
  "layout_preset": "thumb.text_left_image_right",
  "background_url": "https://cdn/.../dalle_bg.png",
  "title": {
    "text": "Why You SHIVER",
    "font": "Montserrat",
    "weight": 900,
    "size": 120,
    "color": "#FFFFFF",
    "stroke": { "color": "#000000", "width": 8 },
    "animation": null
  },
  "accent_shapes": [
    { "type": "arrow", "color": "#FF0000", "position": "bottom_right" }
  ],
  "face_cutout_url": null,
  "format": "png",
  "width": 1280,
  "height": 720
}
```

---

## 4. Zod schema (runtime validation)

```ts
// src/schemas/directionV3.ts
import { z } from "zod";
import { TRANSITION_PRESETS } from "../registry/transitions";
import { ANIMATION_PRESETS } from "../registry/animations";
import { SCENE_PRESETS } from "../registry/scenes";
import { EFFECT_PRESETS } from "../registry/effects";
import { OVERLAY_PRESETS } from "../registry/overlays";

const transitionId = z.enum(Object.keys(TRANSITION_PRESETS) as [string, ...string[]]);
const animationId = z.enum(Object.keys(ANIMATION_PRESETS) as [string, ...string[]]);
const sceneId = z.enum(Object.keys(SCENE_PRESETS) as [string, ...string[]]);
const effectId = z.enum(Object.keys(EFFECT_PRESETS) as [string, ...string[]]);
const overlayId = z.enum(Object.keys(OVERLAY_PRESETS) as [string, ...string[]]);

const PresetRef = <T extends z.ZodTypeAny>(idSchema: T) =>
  z.object({
    preset: idSchema,
    overrides: z.record(z.unknown()).optional(),
  });

const Animation = z.object({
  preset: animationId,
  target: z.string().optional(),
  overrides: z.record(z.unknown()).optional(),
});

const Segment = z.object({
  id: z.string(),
  start_ms: z.number().int().nonnegative(),
  duration_ms: z.number().int().positive(),
  scene_preset: sceneId,
  scene_overrides: z.record(z.unknown()).optional(),
  animations_in: z.array(Animation).optional(),
  animations_out: z.array(Animation).optional(),
  effects: z.array(effectId).optional(),
  overlays: z.array(PresetRef(overlayId)).optional(),
  sfx: z
    .array(
      z.object({
        preset: z.string(),
        at_ms: z.number().int().nonnegative(),
      }),
    )
    .optional(),
  transition_out: PresetRef(transitionId).optional(),
});

export const DirectionV3 = z.object({
  version: z.literal("3.0"),
  meta: z.object({
    video_id: z.string(),
    channel_id: z.string(),
    title: z.string(),
    duration_target_seconds: z.number().positive(),
    aspect: z.enum(["16:9", "9:16", "1:1"]),
    fps: z.number().int().positive(),
    resolution: z.object({
      width: z.number().int().positive(),
      height: z.number().int().positive(),
    }),
  }),
  template: z.string(),
  theme: z.object({
    primary_color: z.string(),
    accent_color: z.string(),
    background_color: z.string(),
    text_color: z.string(),
    fonts: z.object({ heading: z.string(), body: z.string() }),
  }),
  grade_preset: effectId,
  global_effects: z.array(effectId).optional(),
  global_overlays: z.array(PresetRef(overlayId)).optional(),
  audio: z.object({
    voiceover_url: z.string().url(),
    voiceover_srt_url: z.string().url().optional(),
    music_url: z.string().url().optional(),
    music_volume_db: z.number().optional(),
    ducking: z
      .object({
        enabled: z.boolean(),
        threshold_db: z.number(),
        attack_ms: z.number(),
        release_ms: z.number(),
      })
      .optional(),
    loudness_target_lufs: z.number().optional(),
  }),
  branding: z
    .object({
      intro_preset: z.string().optional(),
      outro_preset: z.string().optional(),
      watermark: PresetRef(overlayId).optional(),
    })
    .optional(),
  segments: z.array(Segment).min(1),
  thumbnail: z
    .object({
      composition: z.literal("ThumbnailComp"),
      layout_preset: z.string(),
      background_url: z.string().url(),
      title: z.object({
        text: z.string(),
        font: z.string(),
        weight: z.number(),
        size: z.number(),
        color: z.string(),
        stroke: z.object({ color: z.string(), width: z.number() }).optional(),
      }),
      format: z.enum(["png", "jpg"]),
      width: z.number().int().positive(),
      height: z.number().int().positive(),
    })
    .optional(),
});

export type DirectionV3Input = z.infer<typeof DirectionV3>;
```

---

## 5. Template-aware validator

Beyond schema, enforce template rules (forbidden transitions, ratio budgets).

```ts
// src/utils/compositionValidator.ts
import type { DirectionV3Input } from "../schemas/directionV3";
import { TEMPLATES } from "../templates";

export function validateAgainstTemplate(d: DirectionV3Input) {
  const tpl = TEMPLATES[d.template];
  if (!tpl) throw new Error(`Unknown template: ${d.template}`);

  const errors: string[] = [];
  const warnings: string[] = [];

  // forbidden transitions
  for (const seg of d.segments) {
    const tId = seg.transition_out?.preset;
    if (tId && tpl.forbidden_transitions?.some((p) => tId.startsWith(p))) {
      errors.push(`Segment ${seg.id} uses forbidden transition ${tId} for template ${d.template}`);
    }
  }

  // scene-type ratio budgets
  const totalMs = d.segments.reduce((a, s) => a + s.duration_ms, 0);
  const byCat: Record<string, number> = {};
  for (const s of d.segments) {
    const cat = s.scene_preset.split(".")[1]; // e.g. "stock", "kinetic", "data"
    byCat[cat] = (byCat[cat] ?? 0) + s.duration_ms;
  }

  for (const [cat, [min, max]] of Object.entries(tpl.ratio_budgets ?? {})) {
    const ratio = (byCat[cat] ?? 0) / totalMs;
    if (ratio < min) warnings.push(`${cat} ratio ${ratio.toFixed(2)} < target ${min}`);
    if (ratio > max) warnings.push(`${cat} ratio ${ratio.toFixed(2)} > target ${max}`);
  }

  return { errors, warnings, valid: errors.length === 0 };
}
```

---

## 6. Template file (example)

```ts
// src/templates/hybrid-kinetic.ts
export default {
  id: "hybrid-kinetic",
  ratio_budgets: {
    stock: [0.35, 0.5],
    kinetic: [0.25, 0.35],
    data: [0.1, 0.15],
  },
  cuts_per_minute: [8, 14],
  allowed_transitions: ["trans.cut", "trans.slide", "trans.zoom", "trans.dissolve"],
  forbidden_transitions: ["trans.glitch", "trans.shatter"],
  default_grade: "fx.grade.cinematic_teal_orange",
  default_caption: "ov.caption.word_highlight_yellow",
  default_music_style: "cinematic_with_beats",
};
```

---

## 7. Why preset-ID references over inline props

| Concern            | Inline props               | Preset IDs                        |
| ------------------ | -------------------------- | --------------------------------- |
| LLM prompt size    | Huge, complex nested props | Small enum of strings             |
| LLM accuracy       | Often hallucinates props   | Constrained to valid IDs          |
| Visual consistency | Each call may vary         | Guaranteed design-system fidelity |
| Iterate on design  | Edit every JSON            | Edit one registry entry           |
| A/B testing        | Impossible                 | Swap preset IDs                   |
| Marketplace        | Hard                       | Trivial (JSON-only)               |

---

## 8. Migration from v2 (if you have one)

- v2 segment `{type: "stock_video", props: {...}}` → v3 `{scene_preset: "scene.stock.kenburns_slow", scene_overrides: {...}}`
- v2 transition strings `"slide_left"` → v3 `"trans.slide.left.fast"`
- v2 animations `{type: "scale_punch"}` → v3 `{preset: "anim.in.scale_punch"}`

A codemod can be written once registry is stable.

---

## 9. Example: minimal valid document

```json
{
  "version": "3.0",
  "meta": {
    "video_id": "v1",
    "channel_id": "c1",
    "title": "Test",
    "duration_target_seconds": 10,
    "aspect": "16:9",
    "fps": 30,
    "resolution": { "width": 1920, "height": 1080 }
  },
  "template": "hybrid-kinetic",
  "theme": {
    "primary_color": "#FF3B30",
    "accent_color": "#FFD60A",
    "background_color": "#000",
    "text_color": "#FFF",
    "fonts": { "heading": "Montserrat", "body": "Inter" }
  },
  "grade_preset": "fx.grade.cinematic_teal_orange",
  "audio": { "voiceover_url": "https://cdn/vo.mp3" },
  "segments": [
    {
      "id": "s1",
      "start_ms": 0,
      "duration_ms": 5000,
      "scene_preset": "scene.kinetic.scale_punch",
      "scene_overrides": { "text": "Hello World" }
    }
  ]
}
```

This validates → renders → uploads. Minimum contract.
