import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { linearTiming, springTiming } from "@remotion/transitions";
import { blurSwap, iris, whipPan, cover, zoomPunch, glitchCut, shatter, morph } from "./customTransitions";
import { zoomPunchTransition } from "../components/transitions/ZoomPunchTransition";
import { flashTransition } from "../components/transitions/FlashTransition";
import type { TransitionRegistry } from "./transitionTypes";

/**
 * Phase 1: 15 transition presets built on @remotion/transitions primitives.
 * "Cut" is modeled as a zero-duration linearTiming + fade — the simplest no-op.
 * "Zoom" / "Flash" are not in @remotion/transitions; approximated via fade
 * (Phase 3 will add custom presenters).
 */
export const TRANSITION_PRESETS: TransitionRegistry = {
  // --- Cut ---
  "trans.cut": {
    id: "trans.cut",
    category: "transition",
    tags: ["instant"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 1 }),
    }),
  },

  // --- Dissolve (fade) ---
  "trans.dissolve.fast": {
    id: "trans.dissolve.fast",
    category: "transition",
    tags: ["soft"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 8 }),
    }),
  },
  "trans.dissolve.smooth": {
    id: "trans.dissolve.smooth",
    category: "transition",
    tags: ["soft", "cinematic"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 20 }),
    }),
  },

  // --- Slide (4 dirs × fast) ---
  "trans.slide.left.fast": {
    id: "trans.slide.left.fast",
    category: "transition",
    tags: ["snappy"],
    build: () => ({
      presentation: slide({ direction: "from-right" }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.slide.right.fast": {
    id: "trans.slide.right.fast",
    category: "transition",
    tags: ["snappy"],
    build: () => ({
      presentation: slide({ direction: "from-left" }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.slide.up.fast": {
    id: "trans.slide.up.fast",
    category: "transition",
    tags: ["snappy", "vertical"],
    build: () => ({
      presentation: slide({ direction: "from-bottom" }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.slide.down.fast": {
    id: "trans.slide.down.fast",
    category: "transition",
    tags: ["snappy", "vertical"],
    build: () => ({
      presentation: slide({ direction: "from-top" }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.slide.left.smooth": {
    id: "trans.slide.left.smooth",
    category: "transition",
    tags: ["smooth"],
    build: () => ({
      presentation: slide({ direction: "from-right" }),
      timing: springTiming({ config: { damping: 200 }, durationInFrames: 22 }),
    }),
  },
  "trans.slide.right.smooth": {
    id: "trans.slide.right.smooth",
    category: "transition",
    tags: ["smooth"],
    build: () => ({
      presentation: slide({ direction: "from-left" }),
      timing: springTiming({ config: { damping: 200 }, durationInFrames: 22 }),
    }),
  },

  // --- Wipe (approximates "zoom-in" feel when we need a directional cut-in) ---
  "trans.wipe.left": {
    id: "trans.wipe.left",
    category: "transition",
    tags: ["wipe"],
    build: () => ({
      presentation: wipe({ direction: "from-right" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.wipe.right": {
    id: "trans.wipe.right",
    category: "transition",
    tags: ["wipe"],
    build: () => ({
      presentation: wipe({ direction: "from-left" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },

  // --- Zoom-punch (fallback to fast fade for Phase 1; custom in Phase 3) ---
  "trans.zoom.punch_hard": {
    id: "trans.zoom.punch_hard",
    category: "transition",
    tags: ["punch", "fallback"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 4 }),
    }),
  },
  "trans.zoom.punch_soft": {
    id: "trans.zoom.punch_soft",
    category: "transition",
    tags: ["punch", "fallback"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 8 }),
    }),
  },

  // --- Flash (white quick fade — Phase 3 replaces with proper flash frame) ---
  "trans.flash.white": {
    id: "trans.flash.white",
    category: "transition",
    tags: ["impact", "fallback"],
    build: () => ({
      presentation: fade(),
      timing: linearTiming({ durationInFrames: 3 }),
    }),
  },

  // --- Flip (bonus) ---
  "trans.flip.x": {
    id: "trans.flip.x",
    category: "transition",
    tags: ["flip", "bonus"],
    build: () => ({
      presentation: flip({ direction: "from-right" }),
      timing: linearTiming({ durationInFrames: 16 }),
    }),
  },

  // --- Phase 2: Push (both scenes slide together — @remotion slide does this) ---
  "trans.push.left": {
    id: "trans.push.left", category: "transition", tags: ["push"],
    build: () => ({
      presentation: slide({ direction: "from-right" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.push.right": {
    id: "trans.push.right", category: "transition", tags: ["push"],
    build: () => ({
      presentation: slide({ direction: "from-left" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.push.up": {
    id: "trans.push.up", category: "transition", tags: ["push", "vertical"],
    build: () => ({
      presentation: slide({ direction: "from-bottom" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },

  // --- Phase 2: Cover (incoming slides over stationary outgoing) ---
  "trans.cover.left": {
    id: "trans.cover.left", category: "transition", tags: ["cover"],
    build: () => ({
      presentation: cover({ dir: "right" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.cover.right": {
    id: "trans.cover.right", category: "transition", tags: ["cover"],
    build: () => ({
      presentation: cover({ dir: "left" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.cover.up": {
    id: "trans.cover.up", category: "transition", tags: ["cover", "vertical"],
    build: () => ({
      presentation: cover({ dir: "down" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },

  // --- Phase 2: Wipe (extra directions) ---
  "trans.wipe.up": {
    id: "trans.wipe.up", category: "transition", tags: ["wipe", "vertical"],
    build: () => ({
      presentation: wipe({ direction: "from-bottom" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.wipe.down": {
    id: "trans.wipe.down", category: "transition", tags: ["wipe", "vertical"],
    build: () => ({
      presentation: wipe({ direction: "from-top" }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },

  // --- Phase 2: Iris ---
  "trans.iris.open": {
    id: "trans.iris.open", category: "transition", tags: ["iris", "reveal"],
    build: () => ({
      presentation: iris({ direction: "open" }),
      timing: linearTiming({ durationInFrames: 20 }),
    }),
  },
  "trans.iris.close": {
    id: "trans.iris.close", category: "transition", tags: ["iris"],
    build: () => ({
      presentation: iris({ direction: "close" }),
      timing: linearTiming({ durationInFrames: 20 }),
    }),
  },

  // --- Phase 2: BlurSwap ---
  "trans.blurswap.soft": {
    id: "trans.blurswap.soft", category: "transition", tags: ["blur", "soft"],
    build: () => ({
      presentation: blurSwap({ maxBlurPx: 20 }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.blurswap.hard": {
    id: "trans.blurswap.hard", category: "transition", tags: ["blur"],
    build: () => ({
      presentation: blurSwap({ maxBlurPx: 50 }),
      timing: linearTiming({ durationInFrames: 18 }),
    }),
  },

  // --- Phase 2: WhipPan ---
  "trans.whippan.left": {
    id: "trans.whippan.left", category: "transition", tags: ["whippan", "snappy"],
    build: () => ({
      presentation: whipPan({ dir: "left", maxBlurPx: 24 }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.whippan.right": {
    id: "trans.whippan.right", category: "transition", tags: ["whippan", "snappy"],
    build: () => ({
      presentation: whipPan({ dir: "right", maxBlurPx: 24 }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },

  // --- Phase 3: Premium transitions ---
  "trans.zoompunch.hard": {
    id: "trans.zoompunch.hard", category: "transition", tags: ["punch", "premium"],
    build: () => ({
      presentation: zoomPunch({ maxZoom: 2.8, maxBlurPx: 20 }),
      timing: linearTiming({ durationInFrames: 6 }),
    }),
  },
  "trans.zoompunch.soft": {
    id: "trans.zoompunch.soft", category: "transition", tags: ["punch", "premium"],
    build: () => ({
      presentation: zoomPunch({ maxZoom: 1.8, maxBlurPx: 12 }),
      timing: linearTiming({ durationInFrames: 12 }),
    }),
  },
  "trans.glitchcut.mild": {
    id: "trans.glitchcut.mild", category: "transition", tags: ["glitch", "premium"],
    build: () => ({
      presentation: glitchCut({ splitPx: 10 }),
      timing: linearTiming({ durationInFrames: 6 }),
    }),
  },
  "trans.glitchcut.heavy": {
    id: "trans.glitchcut.heavy", category: "transition", tags: ["glitch", "premium"],
    build: () => ({
      presentation: glitchCut({ splitPx: 28 }),
      timing: linearTiming({ durationInFrames: 8 }),
    }),
  },
  "trans.shatter.grid": {
    id: "trans.shatter.grid", category: "transition", tags: ["shatter", "premium"],
    build: () => ({
      presentation: shatter({ cols: 8, rows: 5 }),
      timing: linearTiming({ durationInFrames: 22 }),
    }),
  },
  "trans.shatter.fine": {
    id: "trans.shatter.fine", category: "transition", tags: ["shatter", "premium"],
    build: () => ({
      presentation: shatter({ cols: 14, rows: 9 }),
      timing: linearTiming({ durationInFrames: 26 }),
    }),
  },
  "trans.morph.subtle": {
    id: "trans.morph.subtle", category: "transition", tags: ["morph", "premium"],
    build: () => ({
      presentation: morph({ scaleAmt: 0.05, blurPx: 6 }),
      timing: linearTiming({ durationInFrames: 14 }),
    }),
  },
  "trans.morph.strong": {
    id: "trans.morph.strong", category: "transition", tags: ["morph", "premium"],
    build: () => ({
      presentation: morph({ scaleAmt: 0.12, blurPx: 14 }),
      timing: linearTiming({ durationInFrames: 18 }),
    }),
  },

  // --- Premium Zoom Punch ---
  "trans.zoom.punch_in": {
    id: "trans.zoom.punch_in", category: "transition", tags: ["zoom", "premium", "impact"],
    build: (overrides) => ({
      presentation: zoomPunchTransition({ intensity: 2.5, flash: true, direction: "in", ...overrides }),
      timing: linearTiming({ durationInFrames: 12 }),
    }),
  },
  "trans.zoom.punch_out": {
    id: "trans.zoom.punch_out", category: "transition", tags: ["zoom", "premium", "impact"],
    build: (overrides) => ({
      presentation: zoomPunchTransition({ intensity: 2.5, flash: true, direction: "out", ...overrides }),
      timing: linearTiming({ durationInFrames: 12 }),
    }),
  },
  "trans.zoom.aggressive": {
    id: "trans.zoom.aggressive", category: "transition", tags: ["zoom", "premium", "aggressive"],
    build: (overrides) => ({
      presentation: zoomPunchTransition({ intensity: 3.5, flash: true, direction: "in", ...overrides }),
      timing: linearTiming({ durationInFrames: 8 }),
    }),
  },

  // --- Premium Flash ---
  "trans.flash.white_premium": {
    id: "trans.flash.white_premium", category: "transition", tags: ["flash", "premium", "impact"],
    build: (overrides) => ({
      presentation: flashTransition({ color: "#FFFFFF", intensity: 1.0, peakDuration: 0.15, ...overrides }),
      timing: linearTiming({ durationInFrames: 10 }),
    }),
  },
  "trans.flash.color": {
    id: "trans.flash.color", category: "transition", tags: ["flash", "premium", "color"],
    build: (overrides) => ({
      presentation: flashTransition({ color: "#FF3B30", intensity: 0.9, peakDuration: 0.2, ...overrides }),
      timing: linearTiming({ durationInFrames: 12 }),
    }),
  },
};

export function resolveTransition(id: string) {
  return TRANSITION_PRESETS[id] ?? null;
}
