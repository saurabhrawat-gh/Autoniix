import { FadeIn } from "../components/animations/FadeIn";
import { SlideIn } from "../components/animations/SlideIn";
import { ScaleIn } from "../components/animations/ScaleIn";
import { Typewriter } from "../components/animations/Typewriter";
import { BouncePop } from "../components/animations/BouncePop";
import { CountUp } from "../components/animations/CountUp";
import { BlurIn } from "../components/animations/BlurIn";
import { FlipIn } from "../components/animations/FlipIn";
import { ElasticIn } from "../components/animations/ElasticIn";
import { Pulse } from "../components/animations/Pulse";
import { WaveText } from "../components/animations/WaveText";
import { Shake } from "../components/animations/Shake";
// Phase 1B
import { ScrambleDecode } from "../components/animations/ScrambleDecode";
import { PathFollow } from "../components/animations/PathFollow";
import { StaggerWords } from "../components/animations/StaggerWords";
import type { PresetRegistry } from "./types";

/**
 * Phase 1: 6 primitives → 15 named presets. Preset IDs use `anim.in.*` /
 * `anim.out.*` / `anim.emph.*` / `anim.text.*` namespaces per doc A.
 */
export const ANIMATION_PRESETS: PresetRegistry = {
  // --- FadeIn ---
  "anim.in.fade": {
    id: "anim.in.fade",
    component: FadeIn,
    defaultProps: { durationInFrames: 15, ease: "power2" },
    category: "animation",
    tags: ["entrance", "fade"],
  },
  "anim.in.fade_slow": {
    id: "anim.in.fade_slow",
    component: FadeIn,
    defaultProps: { durationInFrames: 30, ease: "sine" },
    category: "animation",
    tags: ["entrance", "fade", "slow"],
  },

  // --- SlideIn (4 dirs) ---
  "anim.in.slide.up": {
    id: "anim.in.slide.up",
    component: SlideIn,
    defaultProps: { direction: "up", durationInFrames: 18, ease: "power3" },
    category: "animation",
    tags: ["entrance", "slide"],
  },
  "anim.in.slide.down": {
    id: "anim.in.slide.down",
    component: SlideIn,
    defaultProps: { direction: "down", durationInFrames: 18, ease: "power3" },
    category: "animation",
    tags: ["entrance", "slide"],
  },
  "anim.in.slide.left": {
    id: "anim.in.slide.left",
    component: SlideIn,
    defaultProps: { direction: "left", durationInFrames: 18, ease: "power3" },
    category: "animation",
    tags: ["entrance", "slide"],
  },
  "anim.in.slide.right": {
    id: "anim.in.slide.right",
    component: SlideIn,
    defaultProps: { direction: "right", durationInFrames: 18, ease: "power3" },
    category: "animation",
    tags: ["entrance", "slide"],
  },

  // --- ScaleIn ---
  "anim.in.scale_soft": {
    id: "anim.in.scale_soft",
    component: ScaleIn,
    defaultProps: { from: 0.9, durationInFrames: 15, ease: "power2" },
    category: "animation",
    tags: ["entrance", "scale"],
  },
  "anim.in.scale_punch": {
    id: "anim.in.scale_punch",
    component: ScaleIn,
    defaultProps: { from: 0, overshoot: 0.15, durationInFrames: 14, ease: "back" },
    category: "animation",
    tags: ["entrance", "scale", "punch"],
  },

  // --- Typewriter ---
  "anim.in.typewriter_fast": {
    id: "anim.in.typewriter_fast",
    component: Typewriter,
    defaultProps: { cps: 40, cursor: true },
    category: "animation",
    tags: ["text", "typewriter"],
  },
  "anim.in.typewriter_slow": {
    id: "anim.in.typewriter_slow",
    component: Typewriter,
    defaultProps: { cps: 15, cursor: true },
    category: "animation",
    tags: ["text", "typewriter"],
  },

  // --- BouncePop ---
  "anim.in.bounce_pop": {
    id: "anim.in.bounce_pop",
    component: BouncePop,
    defaultProps: { damping: 10, mass: 0.5, stiffness: 120 },
    category: "animation",
    tags: ["entrance", "bounce", "playful"],
  },
  "anim.in.bounce_hard": {
    id: "anim.in.bounce_hard",
    component: BouncePop,
    defaultProps: { damping: 8, mass: 0.6, stiffness: 180 },
    category: "animation",
    tags: ["entrance", "bounce"],
  },

  // --- CountUp ---
  "anim.text.count_up": {
    id: "anim.text.count_up",
    component: CountUp,
    defaultProps: { from: 0, to: 100, durationInFrames: 60, ease: "power2" },
    category: "animation",
    tags: ["text", "count"],
  },
  "anim.text.count_up_fast": {
    id: "anim.text.count_up_fast",
    component: CountUp,
    defaultProps: { from: 0, to: 100, durationInFrames: 30, ease: "power3" },
    category: "animation",
    tags: ["text", "count"],
  },
  "anim.text.count_up_decimal": {
    id: "anim.text.count_up_decimal",
    component: CountUp,
    defaultProps: { from: 0, to: 100, durationInFrames: 60, decimals: 1, ease: "power2" },
    category: "animation",
    tags: ["text", "count"],
  },

  // --- Phase 2: BlurIn ---
  "anim.in.blur_soft": {
    id: "anim.in.blur_soft",
    component: BlurIn,
    defaultProps: { durationInFrames: 18, fromBlurPx: 12, ease: "power2" },
    category: "animation",
    tags: ["entrance", "blur"],
  },
  "anim.in.blur_hard": {
    id: "anim.in.blur_hard",
    component: BlurIn,
    defaultProps: { durationInFrames: 22, fromBlurPx: 40, ease: "power3" },
    category: "animation",
    tags: ["entrance", "blur"],
  },

  // --- Phase 2: FlipIn ---
  "anim.in.flip_y": {
    id: "anim.in.flip_y",
    component: FlipIn,
    defaultProps: { axis: "y", durationInFrames: 20, ease: "back" },
    category: "animation",
    tags: ["entrance", "flip"],
  },
  "anim.in.flip_x": {
    id: "anim.in.flip_x",
    component: FlipIn,
    defaultProps: { axis: "x", durationInFrames: 20, ease: "back" },
    category: "animation",
    tags: ["entrance", "flip"],
  },

  // --- Phase 2: ElasticIn ---
  "anim.in.elastic": {
    id: "anim.in.elastic",
    component: ElasticIn,
    defaultProps: { damping: 5, mass: 0.4, stiffness: 90 },
    category: "animation",
    tags: ["entrance", "elastic"],
  },
  "anim.in.elastic_soft": {
    id: "anim.in.elastic_soft",
    component: ElasticIn,
    defaultProps: { damping: 10, mass: 0.6, stiffness: 110 },
    category: "animation",
    tags: ["entrance", "elastic"],
  },

  // --- Phase 2: Pulse (emphasis) ---
  "anim.emph.pulse_slow": {
    id: "anim.emph.pulse_slow",
    component: Pulse,
    defaultProps: { bpm: 60, amplitude: 0.04 },
    category: "animation",
    tags: ["emphasis", "pulse"],
  },
  "anim.emph.pulse_fast": {
    id: "anim.emph.pulse_fast",
    component: Pulse,
    defaultProps: { bpm: 140, amplitude: 0.08 },
    category: "animation",
    tags: ["emphasis", "pulse"],
  },

  // --- Phase 2: WaveText ---
  "anim.text.wave_soft": {
    id: "anim.text.wave_soft",
    component: WaveText,
    defaultProps: { amplitudePx: 10, speed: 1, wavelengthChars: 8 },
    category: "animation",
    tags: ["text", "wave"],
  },
  "anim.text.wave_bold": {
    id: "anim.text.wave_bold",
    component: WaveText,
    defaultProps: { amplitudePx: 20, speed: 1.5, wavelengthChars: 5 },
    category: "animation",
    tags: ["text", "wave"],
  },

  // --- Phase 2: Shake (emphasis / reaction) ---
  "anim.emph.shake_subtle": {
    id: "anim.emph.shake_subtle",
    component: Shake,
    defaultProps: { intensity: 4, rotationDeg: 0.5, durationInFrames: 20 },
    category: "animation",
    tags: ["emphasis", "shake"],
  },
  "anim.emph.shake_hard": {
    id: "anim.emph.shake_hard",
    component: Shake,
    defaultProps: { intensity: 16, rotationDeg: 2, durationInFrames: 30 },
    category: "animation",
    tags: ["emphasis", "shake", "impact"],
  },

  // --- Phase 1B: ScrambleDecode (Mr. Robot style glyph cycling) ---
  "anim.text.scramble_decode": {
    id: "anim.text.scramble_decode",
    component: ScrambleDecode,
    defaultProps: {
      durationInFrames: 30,
      revealMode: "left_to_right" as const,
      scrambleFps: 24,
    },
    category: "animation",
    tags: ["text", "scramble", "decode", "glitch"],
  },
  "anim.text.scramble_random": {
    id: "anim.text.scramble_random",
    component: ScrambleDecode,
    defaultProps: {
      durationInFrames: 36,
      revealMode: "random" as const,
      scrambleFps: 30,
    },
    category: "animation",
    tags: ["text", "scramble", "decode", "random"],
  },

  // --- Phase 1B: PathFollow (text along a Bezier curve) ---
  "anim.text.path_follow": {
    id: "anim.text.path_follow",
    component: PathFollow,
    defaultProps: {
      spreadFrom: 0,
      spreadTo: 1,
      durationInFrames: 40,
      alignToPath: true,
      fontSizePx: 32,
      fontWeight: 600,
    },
    category: "animation",
    tags: ["text", "path", "calligraphy"],
  },

  // --- Phase 1B: StaggerWords (per-word staggered reveal) ---
  "anim.text.stagger_slide_up": {
    id: "anim.text.stagger_slide_up",
    component: StaggerWords,
    defaultProps: {
      delayPerWordInFrames: 4,
      wordDurationInFrames: 12,
      childAnim: "slide_up" as const,
      easing: "ease_out_cubic" as const,
    },
    category: "animation",
    tags: ["text", "stagger", "reveal"],
  },
  "anim.text.stagger_scale_pop": {
    id: "anim.text.stagger_scale_pop",
    component: StaggerWords,
    defaultProps: {
      delayPerWordInFrames: 5,
      wordDurationInFrames: 14,
      childAnim: "scale_pop" as const,
      easing: "ease_out_cubic" as const,
    },
    category: "animation",
    tags: ["text", "stagger", "punch"],
  },
};
