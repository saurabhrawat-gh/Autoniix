/**
 * Phase 1B — Pure compute layer for advanced text animations.
 *
 * Every function is:
 *   • Pure (no DOM, no Remotion hooks, no time of day).
 *   • Deterministic given `(params, t_local_ms)`.
 *   • Importable from non-React contexts (smoke tests, FCPXML exporter, agents).
 *
 * The React components in `components/animations/*.tsx` wrap these functions
 * for rendering, but the IR contract is the *output shape* of these computes
 * — not the React tree.
 *
 * The 6 Phase-1B animations:
 *   1. count_up        (already shipped — see CountUp.tsx; expose pure compute)
 *   2. typewriter      (already shipped — see Typewriter.tsx; expose pure compute)
 *   3. scramble_decode (new — letters cycle then resolve, left→right)
 *   4. path_follow     (new — text glyphs aligned along an SVG bezier path)
 *   5. stagger_words   (new — per-word delayed reveal driving any child anim)
 *   6. wave            (already shipped — see WaveText.tsx; expose pure compute)
 */

/** FNV-1a 32-bit hash — browser-safe, no crypto dep, deterministic seed generator. */
function stableSeed(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  const lo = (h >>> 0).toString(16).padStart(8, "0");
  const hi = ((input.length * 0x9e3779b9) >>> 0).toString(16).padStart(8, "0");
  return (lo + hi).slice(0, 16);
}

/* ====================================================================== */
/* Shared utilities                                                       */
/* ====================================================================== */

/** Clamp helper. */
function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

/** Deterministic 32-bit RNG (mulberry32) seeded by a string. */
export function seededRng(seed: string | number): () => number {
  let h = typeof seed === "number" ? seed >>> 0 : 0;
  if (typeof seed === "string") {
    h = 0x811c9dc5;
    for (let i = 0; i < seed.length; i++) {
      h ^= seed.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
  }
  return function next() {
    h = (h + 0x6d2b79f5) >>> 0;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Common easings used across animations. */
export const EASINGS = {
  linear: (t: number) => t,
  ease_out_cubic: (t: number) => 1 - Math.pow(1 - t, 3),
  ease_in_cubic: (t: number) => t * t * t,
  ease_in_out_cubic: (t: number) =>
    t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  power2: (t: number) => 1 - Math.pow(1 - t, 2),
  power3: (t: number) => 1 - Math.pow(1 - t, 3),
} as const;
export type EasingName = keyof typeof EASINGS;

/* ====================================================================== */
/* 1. count_up                                                            */
/* ====================================================================== */

export interface CountUpParams {
  fromValue: number;
  toValue: number;
  durationMs: number;
  /** printf-like; `${value}` substituted with formatted number. Default: `${value}`. */
  format?: string;
  /** Decimal places when formatting. Default: inferred from `toValue`. */
  decimals?: number;
  easing?: EasingName;
  /** Optional delay before counting starts. Default: 0. */
  delayMs?: number;
}

export interface CountUpFrame {
  value: number;
  text: string;
  progress: number;
}

export function computeCountUp(params: CountUpParams, tLocalMs: number): CountUpFrame {
  const delay = params.delayMs ?? 0;
  const eased = EASINGS[params.easing ?? "ease_out_cubic"];
  const t = clamp((tLocalMs - delay) / Math.max(1, params.durationMs), 0, 1);
  const eT = eased(t);
  const value = params.fromValue + (params.toValue - params.fromValue) * eT;
  const decimals =
    params.decimals ??
    (Number.isInteger(params.fromValue) && Number.isInteger(params.toValue) ? 0 : 2);
  const formatted = value.toFixed(decimals);
  const text = (params.format ?? "${value}").replace("${value}", formatted);
  return { value, text, progress: t };
}

/* ====================================================================== */
/* 2. typewriter                                                          */
/* ====================================================================== */

export interface TypewriterParams {
  text: string;
  cps?: number;
  delayMs?: number;
  cursorChar?: string;
  cursorBlinkMs?: number;
}

export interface TypewriterFrame {
  visible: string;
  showCursor: boolean;
  progress: number;
}

export function computeTypewriter(
  params: TypewriterParams,
  tLocalMs: number,
): TypewriterFrame {
  const cps = params.cps ?? 30;
  const delay = params.delayMs ?? 0;
  const elapsedSec = Math.max(0, (tLocalMs - delay) / 1000);
  const chars = Math.min(params.text.length, Math.floor(elapsedSec * cps));
  const cursorBlinkMs = params.cursorBlinkMs ?? 500;
  const cursorPhase = Math.floor(tLocalMs / cursorBlinkMs) % 2 === 0;
  return {
    visible: params.text.slice(0, chars),
    showCursor: !!params.cursorChar && cursorPhase,
    progress: params.text.length === 0 ? 1 : chars / params.text.length,
  };
}

/* ====================================================================== */
/* 3. scramble_decode                                                     */
/* ====================================================================== */

export type ScrambleRevealMode = "left_to_right" | "right_to_left" | "center_out" | "random";

export interface ScrambleDecodeParams {
  text: string;
  durationMs: number;
  /** Glyph pool. Default: alphanum + symbols. */
  charset?: string;
  revealMode?: ScrambleRevealMode;
  /** How many glyph swaps per second per char before settling. Default: 24. */
  scrambleFps?: number;
  /** Deterministic seed. Default: hash(text + duration). */
  seed?: string | number;
}

export interface ScrambleDecodeFrame {
  visible: string;
  progress: number;
}

const DEFAULT_CHARSET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-+=";

export function computeScrambleDecode(
  params: ScrambleDecodeParams,
  tLocalMs: number,
): ScrambleDecodeFrame {
  const charset = params.charset ?? DEFAULT_CHARSET;
  const revealMode: ScrambleRevealMode = params.revealMode ?? "left_to_right";
  const scrambleFps = params.scrambleFps ?? 24;
  const seedKey =
    params.seed ??
    stableSeed(`scramble:${params.text}:${params.durationMs}`);

  const text = params.text;
  const N = text.length;
  if (N === 0 || params.durationMs <= 0) {
    return { visible: text, progress: 1 };
  }

  const t = clamp(tLocalMs / params.durationMs, 0, 1);

  const charSettlePerChar = 1 / N;
  function charProgress(i: number): number {
    let order: number;
    switch (revealMode) {
      case "left_to_right":
        order = i;
        break;
      case "right_to_left":
        order = N - 1 - i;
        break;
      case "center_out": {
        const mid = (N - 1) / 2;
        order = Math.floor(Math.abs(i - mid));
        break;
      }
      case "random": {
        const rng = seededRng(`${seedKey}:order`);
        const arr = Array.from({ length: N }, (_, k) => k);
        for (let k = N - 1; k > 0; k--) {
          const j = Math.floor(rng() * (k + 1));
          [arr[k]!, arr[j]!] = [arr[j]!, arr[k]!];
        }
        order = arr.indexOf(i);
        break;
      }
    }
    const start = order * charSettlePerChar;
    const end = start + charSettlePerChar;
    return clamp((t - start) / (end - start), 0, 1);
  }

  const frameBucket = Math.floor((tLocalMs / 1000) * scrambleFps);

  const out: string[] = [];
  for (let i = 0; i < N; i++) {
    const cp = charProgress(i);
    if (cp >= 1) {
      out.push(text[i]!);
    } else {
      const rng = seededRng(`${seedKey}:${i}:${frameBucket}`);
      const idx = Math.floor(rng() * charset.length);
      out.push(charset[idx] ?? text[i]!);
    }
  }
  return { visible: out.join(""), progress: t };
}

/* ====================================================================== */
/* 4. path_follow                                                         */
/* ====================================================================== */

/** Bezier path described as a sequence of cubic segments. */
export interface BezierPath {
  /** Start point. */
  start: [number, number];
  /** Cubic Bezier segments: each [c1, c2, end]. */
  segments: Array<{ c1: [number, number]; c2: [number, number]; end: [number, number] }>;
}

export interface PathFollowParams {
  text: string;
  path: BezierPath;
  /**
   * 0 = align all chars to the start of the path; 1 = chars span the whole path.
   * Used to animate the layout from compressed to extended.
   */
  spread?: number;
  /** Whether glyphs rotate to follow the tangent. Default true. */
  alignToPath?: boolean;
  /** Char width, used to space glyphs along the path. Default 14 px. */
  charSpacingPx?: number;
}

export interface PathFollowGlyph {
  char: string;
  x: number;
  y: number;
  rotationRad: number;
}

function lerp2(a: [number, number], b: [number, number], t: number): [number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

function bezierAt(
  p0: [number, number],
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  t: number,
): { pos: [number, number]; tan: [number, number] } {
  const a = lerp2(p0, p1, t);
  const b = lerp2(p1, p2, t);
  const c = lerp2(p2, p3, t);
  const ab = lerp2(a, b, t);
  const bc = lerp2(b, c, t);
  const pos = lerp2(ab, bc, t);
  const tan: [number, number] = [
    3 * (1 - t) * (1 - t) * (p1[0] - p0[0]) +
      6 * (1 - t) * t * (p2[0] - p1[0]) +
      3 * t * t * (p3[0] - p2[0]),
    3 * (1 - t) * (1 - t) * (p1[1] - p0[1]) +
      6 * (1 - t) * t * (p2[1] - p1[1]) +
      3 * t * t * (p3[1] - p2[1]),
  ];
  return { pos, tan };
}

/**
 * Sample point + tangent along the whole path at parameter `u` ∈ [0, 1].
 * Treats segments uniformly (good enough for typography UX; can be upgraded
 * to arc-length parameterization later).
 */
function samplePath(
  path: BezierPath,
  u: number,
): { pos: [number, number]; tan: [number, number] } {
  if (path.segments.length === 0) {
    return { pos: path.start, tan: [1, 0] };
  }
  const seg = clamp(Math.floor(u * path.segments.length), 0, path.segments.length - 1);
  const localU = u * path.segments.length - seg;
  const s = path.segments[seg]!;
  const prevEnd = seg === 0 ? path.start : path.segments[seg - 1]!.end;
  return bezierAt(prevEnd, s.c1, s.c2, s.end, localU);
}

export function computePathFollow(
  params: PathFollowParams,
  tLocalMs: number,
): PathFollowGlyph[] {
  void tLocalMs;
  const spread = params.spread ?? 1;
  const alignToPath = params.alignToPath ?? true;
  const charSpacing = params.charSpacingPx ?? 14;

  void charSpacing;
  const N = params.text.length;
  const totalSpan = clamp(spread, 0, 1);
  const out: PathFollowGlyph[] = [];
  for (let i = 0; i < N; i++) {
    const u = N === 1 ? 0 : (i / (N - 1)) * totalSpan;
    const { pos, tan } = samplePath(params.path, u);
    out.push({
      char: params.text[i]!,
      x: pos[0],
      y: pos[1],
      rotationRad: alignToPath ? Math.atan2(tan[1], tan[0]) : 0,
    });
  }
  return out;
}

/* ====================================================================== */
/* 5. stagger_words                                                       */
/* ====================================================================== */

export interface StaggerWordsParams {
  words: string[];
  /** Delay between consecutive word starts. */
  delayPerWordMs: number;
  /** Per-word animation duration. */
  wordDurationMs: number;
  easing?: EasingName;
}

export interface StaggerWordsFrame {
  /** Per-word state at `tLocalMs`. */
  perWord: Array<{
    word: string;
    progress: number;
    started: boolean;
    finished: boolean;
  }>;
  /** Whole-clip progress 0..1. */
  progress: number;
}

export function computeStaggerWords(
  params: StaggerWordsParams,
  tLocalMs: number,
): StaggerWordsFrame {
  const eased = EASINGS[params.easing ?? "ease_out_cubic"];
  const total = Math.max(
    1,
    params.words.length * params.delayPerWordMs + params.wordDurationMs,
  );
  const perWord = params.words.map((word, i) => {
    const start = i * params.delayPerWordMs;
    const t = clamp((tLocalMs - start) / Math.max(1, params.wordDurationMs), 0, 1);
    return {
      word,
      progress: eased(t),
      started: tLocalMs >= start,
      finished: t >= 1,
    };
  });
  return { perWord, progress: clamp(tLocalMs / total, 0, 1) };
}

/* ====================================================================== */
/* 6. wave                                                                */
/* ====================================================================== */

export interface WaveParams {
  text: string;
  amplitudePx: number;
  /** Wave temporal frequency in Hz. */
  frequencyHz: number;
  /** Wavelength expressed in characters (phase increment per char). */
  wavelengthChars: number;
}

export interface WaveGlyph {
  char: string;
  /** Vertical offset to apply to the glyph at this frame. */
  yOffsetPx: number;
}

export function computeWave(params: WaveParams, tLocalMs: number): WaveGlyph[] {
  const wavelen = Math.max(0.0001, params.wavelengthChars);
  const phasePerChar = (Math.PI * 2) / wavelen;
  const tPhase = (tLocalMs / 1000) * params.frequencyHz * Math.PI * 2;
  const out: WaveGlyph[] = [];
  for (let i = 0; i < params.text.length; i++) {
    const phase = i * phasePerChar - tPhase;
    out.push({
      char: params.text[i]!,
      yOffsetPx: Math.sin(phase) * params.amplitudePx,
    });
  }
  return out;
}

/* ====================================================================== */
/* Discriminated union — convenient for IR persistence / patching.        */
/* ====================================================================== */

export type AdvancedTextAnim =
  | ({ kind: "count_up" } & CountUpParams)
  | ({ kind: "typewriter" } & TypewriterParams)
  | ({ kind: "scramble_decode" } & ScrambleDecodeParams)
  | ({ kind: "path_follow" } & PathFollowParams)
  | ({ kind: "stagger_words" } & StaggerWordsParams)
  | ({ kind: "wave" } & WaveParams);

/** All Phase-1B animation kinds. */
export const ADVANCED_TEXT_ANIM_KINDS = [
  "count_up",
  "typewriter",
  "scramble_decode",
  "path_follow",
  "stagger_words",
  "wave",
] as const;
export type AdvancedTextAnimKind = (typeof ADVANCED_TEXT_ANIM_KINDS)[number];
