# C. Preset Registry Pattern — Code Examples

> Goal: **one component file → dozens of named presets.** This is how CapCut/Canva multiply their libraries without multiplying code.

---

## 1. Directory layout

```
src/
├── components/
│   ├── transitions/
│   │   ├── Slide.tsx
│   │   ├── Zoom.tsx
│   │   ├── Dissolve.tsx
│   │   └── ...
│   ├── animations/
│   ├── scenes/
│   ├── effects/
│   └── overlays/
│
├── registry/
│   ├── index.ts            # unified exports + resolver
│   ├── transitions.ts      # TRANSITION_PRESETS
│   ├── animations.ts       # ANIMATION_PRESETS
│   ├── scenes.ts           # SCENE_PRESETS
│   ├── effects.ts          # EFFECT_PRESETS
│   ├── overlays.ts         # OVERLAY_PRESETS
│   └── types.ts            # shared PresetID types
│
└── utils/
    └── presetResolver.ts   # resolves "trans.slide.left.fast" → { Component, props }
```

---

## 2. Example component — one `Slide` file → 20+ presets

```tsx
// src/components/transitions/Slide.tsx
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export type SlideDirection = "left" | "right" | "up" | "down";

export interface SlideProps {
  direction: SlideDirection;
  durationInFrames: number;
  ease?: EaseName; // "linear" | "sine" | "power2" | "power3" | "bounce"
  overshoot?: number; // 0 = none, 0.1 = 10% past target then settle
  blur?: boolean; // motion blur while sliding
  children: React.ReactNode;
}

export const Slide: React.FC<SlideProps> = ({
  direction,
  durationInFrames,
  ease = "power2",
  overshoot = 0,
  blur = false,
  children,
}) => {
  const frame = useCurrentFrame();
  const easeFn = easings[ease];

  const progress = easeFn(
    interpolate(frame, [0, durationInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  const settled =
    overshoot > 0 ? interpolate(progress, [0, 0.7, 1], [0, 1 + overshoot, 1]) : progress;

  const axis = direction === "left" || direction === "right" ? "X" : "Y";
  const sign = direction === "left" || direction === "up" ? -1 : 1;
  const offset = (1 - settled) * 100 * sign;

  return (
    <AbsoluteFill
      style={{
        transform: `translate${axis}(${offset}%)`,
        filter: blur ? `blur(${(1 - progress) * 8}px)` : undefined,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
```

---

## 3. Registry file — data-driven presets

```ts
// src/registry/transitions.ts
import { Slide } from "../components/transitions/Slide";
import { Zoom } from "../components/transitions/Zoom";
import { Dissolve } from "../components/transitions/Dissolve";
import { Cut } from "../components/transitions/Cut";
import { Flash } from "../components/transitions/Flash";

export interface PresetEntry<P = Record<string, unknown>> {
  id: string;
  component: React.ComponentType<any>;
  defaultProps: P;
  category: "transition" | "animation" | "scene" | "effect" | "overlay";
  tags: string[];
  thumbnail?: string; // pre-rendered 2s gif path
}

export const TRANSITION_PRESETS: Record<string, PresetEntry> = {
  // --- CUT ---
  "trans.cut": {
    id: "trans.cut",
    component: Cut,
    defaultProps: {},
    category: "transition",
    tags: ["instant", "hard"],
  },

  // --- DISSOLVE (2 speeds) ---
  "trans.dissolve.fast": {
    id: "trans.dissolve.fast",
    component: Dissolve,
    defaultProps: { durationInFrames: 8 },
    category: "transition",
    tags: ["soft", "documentary"],
  },
  "trans.dissolve.smooth": {
    id: "trans.dissolve.smooth",
    component: Dissolve,
    defaultProps: { durationInFrames: 20 },
    category: "transition",
    tags: ["soft", "cinematic"],
  },

  // --- SLIDE (4 dirs × 2 speeds × 2 eases = 16 presets from ONE component) ---
  "trans.slide.left.fast": {
    id: "trans.slide.left.fast",
    component: Slide,
    defaultProps: { direction: "left", durationInFrames: 10, ease: "power3" },
    category: "transition",
    tags: ["snappy", "modern"],
  },
  "trans.slide.left.smooth": {
    id: "trans.slide.left.smooth",
    component: Slide,
    defaultProps: { direction: "left", durationInFrames: 20, ease: "sine" },
    category: "transition",
    tags: ["soft", "cinematic"],
  },
  "trans.slide.left.bounce": {
    id: "trans.slide.left.bounce",
    component: Slide,
    defaultProps: { direction: "left", durationInFrames: 15, ease: "bounce", overshoot: 0.1 },
    category: "transition",
    tags: ["playful", "2d"],
  },
  "trans.slide.right.fast": {
    id: "trans.slide.right.fast",
    component: Slide,
    defaultProps: { direction: "right", durationInFrames: 10, ease: "power3" },
    category: "transition",
    tags: ["snappy"],
  },
  "trans.slide.right.smooth": {
    id: "trans.slide.right.smooth",
    component: Slide,
    defaultProps: { direction: "right", durationInFrames: 20, ease: "sine" },
    category: "transition",
    tags: ["soft"],
  },
  "trans.slide.up.fast": {
    id: "trans.slide.up.fast",
    component: Slide,
    defaultProps: { direction: "up", durationInFrames: 10, ease: "power3" },
    category: "transition",
    tags: ["snappy", "vertical"],
  },
  "trans.slide.down.fast": {
    id: "trans.slide.down.fast",
    component: Slide,
    defaultProps: { direction: "down", durationInFrames: 10, ease: "power3" },
    category: "transition",
    tags: ["snappy", "vertical"],
  },
  "trans.slide.up.blur": {
    id: "trans.slide.up.blur",
    component: Slide,
    defaultProps: { direction: "up", durationInFrames: 14, ease: "power2", blur: true },
    category: "transition",
    tags: ["cinematic", "motion-blur"],
  },
  // ...+8 more slide variants

  // --- ZOOM ---
  "trans.zoom.punch_hard": {
    id: "trans.zoom.punch_hard",
    component: Zoom,
    defaultProps: { scale: 1.5, shake: true, durationInFrames: 8 },
    category: "transition",
    tags: ["aggressive", "punch"],
  },
  "trans.zoom.punch_soft": {
    id: "trans.zoom.punch_soft",
    component: Zoom,
    defaultProps: { scale: 1.15, shake: false, durationInFrames: 12 },
    category: "transition",
    tags: ["subtle"],
  },
  "trans.zoom.out_cinematic": {
    id: "trans.zoom.out_cinematic",
    component: Zoom,
    defaultProps: { scale: 0.7, durationInFrames: 30, ease: "sine" },
    category: "transition",
    tags: ["cinematic", "reveal"],
  },

  // --- FLASH ---
  "trans.flash.white": {
    id: "trans.flash.white",
    component: Flash,
    defaultProps: { color: "#ffffff", durationInFrames: 4 },
    category: "transition",
    tags: ["impact"],
  },
  "trans.flash.accent": {
    id: "trans.flash.accent",
    component: Flash,
    defaultProps: { color: "accent", durationInFrames: 6 },
    category: "transition",
    tags: ["branded"],
  },
};

export type TransitionPresetId = keyof typeof TRANSITION_PRESETS;
```

**One `Slide.tsx` → 16 named "transitions."** Add one more line to the registry, get another.

---

## 4. Central resolver

```ts
// src/utils/presetResolver.ts
import { TRANSITION_PRESETS } from "../registry/transitions";
import { ANIMATION_PRESETS } from "../registry/animations";
import { SCENE_PRESETS } from "../registry/scenes";
import { EFFECT_PRESETS } from "../registry/effects";
import { OVERLAY_PRESETS } from "../registry/overlays";
import type { PresetEntry } from "../registry/transitions";

const ALL_PRESETS: Record<string, PresetEntry> = {
  ...TRANSITION_PRESETS,
  ...ANIMATION_PRESETS,
  ...SCENE_PRESETS,
  ...EFFECT_PRESETS,
  ...OVERLAY_PRESETS,
};

export function resolvePreset(id: string, overrides: Record<string, unknown> = {}) {
  const entry = ALL_PRESETS[id];
  if (!entry) throw new Error(`Unknown preset: ${id}`);
  return {
    Component: entry.component,
    props: { ...entry.defaultProps, ...overrides },
    meta: { category: entry.category, tags: entry.tags },
  };
}

export function listPresets(filter?: { category?: string; tag?: string }) {
  return Object.values(ALL_PRESETS).filter((p) => {
    if (filter?.category && p.category !== filter.category) return false;
    if (filter?.tag && !p.tags.includes(filter.tag)) return false;
    return true;
  });
}
```

---

## 5. Usage in a composition

```tsx
// src/compositions/MainVideo.tsx
import { Series } from "remotion";
import { resolvePreset } from "../utils/presetResolver";
import type { DirectionV3 } from "../types/direction";

export const MainVideo: React.FC<{ direction: DirectionV3 }> = ({ direction }) => {
  return (
    <Series>
      {direction.segments.map((seg, i) => {
        const { Component: Scene, props: sceneProps } = resolvePreset(
          seg.scene_preset,
          seg.scene_overrides,
        );
        const next = direction.segments[i + 1];
        const { Component: Trans, props: transProps } = next
          ? resolvePreset(next.transition_preset ?? "trans.cut")
          : { Component: null as any, props: {} };

        return (
          <Series.Sequence key={i} durationInFrames={seg.duration_frames}>
            <Scene {...sceneProps} {...seg.scene_overrides} />
            {Trans && (
              <Trans {...transProps}>
                <></>
              </Trans>
            )}
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
```

The JSON from your AI director looks like:

```json
{
  "segments": [
    {
      "scene_preset": "scene.stock.kenburns_slow",
      "scene_overrides": { "src": "https://cdn/.../clip1.mp4" },
      "transition_preset": "trans.slide.left.fast",
      "duration_frames": 150
    },
    {
      "scene_preset": "scene.kinetic.scale_punch",
      "scene_overrides": { "text": "78% of Americans" },
      "duration_frames": 90
    }
  ]
}
```

---

## 6. Why this scales

- **Adding a new "transition"** = 4 lines in a registry file. No new imports, no new routing.
- **LLM prompt** is a clean string enum: `scene_preset: "scene.kinetic.scale_punch" | "scene.quote.neon_box" | ...`
- **Preview UI** auto-generates from `listPresets()` — pick by category/tag, render thumbnail.
- **Tests**: one snapshot test per preset ID in CI. If a new preset doesn't render → fail before merge.
- **Marketplace-ready**: ship presets as JSON files that users can import without recompiling.

---

## 7. Variant generator (optional, for CapCut-scale expansion)

Generate 100 presets programmatically:

```ts
// scripts/generate-slide-presets.ts
const dirs = ["left", "right", "up", "down"] as const;
const speeds = { fast: 8, med: 14, smooth: 22 };
const eases = ["linear", "sine", "power2", "power3", "bounce"] as const;

for (const d of dirs)
  for (const [sName, frames] of Object.entries(speeds))
    for (const e of eases)
      console.log(
        `"trans.slide.${d}.${sName}.${e}": { component: Slide, defaultProps: { direction: "${d}", durationInFrames: ${frames}, ease: "${e}" }, category: "transition", tags: [] },`,
      );

// → 4 * 3 * 5 = 60 preset entries from one Slide component.
```

This is exactly how consumer editors claim "100+ transitions" in marketing.
