/**
 * Phase 1D — Pure compute layer for per-shot colour grading.
 *
 * The IR-level type `ColorGradeTrack` is a sequence of keyframes; each carries
 * a `ColorPrimary` (lift / gamma / gain / sat / contrast / temperature / tint),
 * an optional list of `ColorSecondary` regions (HSL qualifier or power
 * window, each with its own primary), and an optional LUT reference.
 *
 * `colorGradeAtTime()` interpolates between adjacent keys and returns a
 * resolved `ColorGradeFrame` ready for shader binding.
 *
 * For the actual pixel transform we provide:
 *   • `applyPrimaryRgb()` — pure RGB-space transform (used by smoke tests and
 *     CPU fallback). Runs in linear-light approximation.
 *   • `hslQualifierWeight()` — shader-equivalent gate function ∈ [0..1]
 *     that scores how much a pixel is "in" an HSL qualifier.
 *   • `powerWindowWeight()` — shader-equivalent gate function ∈ [0..1] for
 *     ellipse / rect / bezier_path power windows.
 *
 * The fragment-shader path lives in `components/effects/ColorGradeWebGL.tsx`
 * (added in this same milestone). Both code paths consume the same compute
 * functions to guarantee CPU and GPU agree at boundary conditions.
 */

import type { MaskShape } from "./masks";

/* ====================================================================== */
/* Types                                                                  */
/* ====================================================================== */

/**
 * Primary correction. All fields optional — defaults make the grade a no-op.
 *   • lift  — RGB shadow offset, default [0,0,0]
 *   • gamma — RGB midtones gain, default [1,1,1]
 *   • gain  — RGB highlights, default [1,1,1]
 *   • saturation — global, default 1.0
 *   • contrast   — pivot-1.0 multiplier, default 1.0
 *   • temperature — kelvin shift in [-100, +100]; positive = warmer
 *   • tint        — magenta-green axis in [-100, +100]; positive = magenta
 */
export interface ColorPrimary {
  lift?: [number, number, number];
  gamma?: [number, number, number];
  gain?: [number, number, number];
  saturation?: number;
  contrast?: number;
  temperature?: number;
  tint?: number;
}

/**
 * HSL qualifier — soft mask over pixels matching a hue/sat/luma range.
 * `hueCenter` in degrees [0..360); `hueWidth` in degrees;
 * sat/lum ranges in [0..1].
 */
export interface HslQualifier {
  kind: "hsl_qualifier";
  hueCenter: number;
  hueWidth: number;
  saturationRange: [number, number];
  luminanceRange: [number, number];
  /** Edge softness in [0..1]; 0 = hard edge, 0.5 ≈ smooth. */
  softness: number;
  grade: ColorPrimary;
}

/**
 * Power window — soft-edge mask over a shape, with its own primary.
 * Reuses the Phase 1C `MaskShape` for ellipse/rect/bezier_path. Luma/chroma
 * shape kinds are NOT allowed here (they're for *cutout* masks; for color
 * grade use `HslQualifier`).
 */
export interface PowerWindow {
  kind: "power_window";
  shape: Exclude<MaskShape, { kind: "luma" } | { kind: "chroma" }>;
  /** Edge softness in [0..1]. */
  softness: number;
  invert?: boolean;
  grade: ColorPrimary;
}

export type ColorSecondary = HslQualifier | PowerWindow;

export interface ColorGradeKey {
  tMs: number;
  primary: ColorPrimary;
  secondaries?: ColorSecondary[];
  lutId?: string;
  /** 0..1; default 1.0 (full LUT). */
  lutStrength?: number;
}

export interface ColorGradeTrack {
  keys: ColorGradeKey[];
}

export interface ColorGradeFrame {
  primary: ColorPrimary;
  secondaries: ColorSecondary[];
  lutId: string | null;
  lutStrength: number;
}

/* ====================================================================== */
/* Validation                                                             */
/* ====================================================================== */

export function validateColorGradeTrack(track: ColorGradeTrack, ctx = "colorGrade"): void {
  if (track.keys.length === 0) {
    throw new Error(`${ctx}: track must have ≥ 1 key`);
  }
  let prev = -Infinity;
  for (const k of track.keys) {
    if (!Number.isFinite(k.tMs)) throw new Error(`${ctx}: tMs must be finite`);
    if (k.tMs < prev) throw new Error(`${ctx}: keys must be sorted by tMs`);
    prev = k.tMs;
    validatePrimary(k.primary, ctx);
    for (const s of k.secondaries ?? []) {
      validateSecondary(s, ctx);
    }
    if (k.lutStrength !== undefined && (k.lutStrength < 0 || k.lutStrength > 1)) {
      throw new Error(`${ctx}: lutStrength out of [0,1]`);
    }
  }
}

function validatePrimary(p: ColorPrimary, ctx: string): void {
  if (p.saturation !== undefined && (!Number.isFinite(p.saturation) || p.saturation < 0)) {
    throw new Error(`${ctx}: saturation must be >= 0`);
  }
  if (p.contrast !== undefined && (!Number.isFinite(p.contrast) || p.contrast < 0)) {
    throw new Error(`${ctx}: contrast must be >= 0`);
  }
  if (p.temperature !== undefined && (p.temperature < -100 || p.temperature > 100)) {
    throw new Error(`${ctx}: temperature must be in [-100,100]`);
  }
  if (p.tint !== undefined && (p.tint < -100 || p.tint > 100)) {
    throw new Error(`${ctx}: tint must be in [-100,100]`);
  }
}

function validateSecondary(s: ColorSecondary, ctx: string): void {
  if (s.softness < 0 || s.softness > 1) {
    throw new Error(`${ctx}: secondary softness out of [0,1]`);
  }
  validatePrimary(s.grade, `${ctx}.secondary`);
  if (s.kind === "hsl_qualifier") {
    if (s.hueWidth < 0 || s.hueWidth > 360) {
      throw new Error(`${ctx}: hsl hueWidth out of [0,360]`);
    }
    const [a, b] = s.saturationRange;
    const [c, d] = s.luminanceRange;
    if (a > b || a < 0 || b > 1) throw new Error(`${ctx}: hsl saturationRange invalid`);
    if (c > d || c < 0 || d > 1) throw new Error(`${ctx}: hsl luminanceRange invalid`);
  }
}

/* ====================================================================== */
/* Interpolation                                                          */
/* ====================================================================== */

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpVec3(
  a: [number, number, number] | undefined,
  b: [number, number, number] | undefined,
  defaultV: [number, number, number],
  t: number,
): [number, number, number] {
  const av = a ?? defaultV;
  const bv = b ?? defaultV;
  return [lerp(av[0], bv[0], t), lerp(av[1], bv[1], t), lerp(av[2], bv[2], t)];
}

function lerpScalar(
  a: number | undefined,
  b: number | undefined,
  defaultV: number,
  t: number,
): number {
  return lerp(a ?? defaultV, b ?? defaultV, t);
}

function lerpPrimary(a: ColorPrimary, b: ColorPrimary, t: number): ColorPrimary {
  return {
    lift: lerpVec3(a.lift, b.lift, [0, 0, 0], t),
    gamma: lerpVec3(a.gamma, b.gamma, [1, 1, 1], t),
    gain: lerpVec3(a.gain, b.gain, [1, 1, 1], t),
    saturation: lerpScalar(a.saturation, b.saturation, 1, t),
    contrast: lerpScalar(a.contrast, b.contrast, 1, t),
    temperature: lerpScalar(a.temperature, b.temperature, 0, t),
    tint: lerpScalar(a.tint, b.tint, 0, t),
  };
}

/**
 * Resolve the grade at any time. Secondaries are NOT interpolated across
 * keys (their identity is unstable across edits); they snap to the previous
 * key's list. This matches DaVinci's behaviour for unmatched node sets.
 */
export function colorGradeAtTime(
  track: ColorGradeTrack,
  tLocalMs: number,
): ColorGradeFrame {
  if (track.keys.length === 0) throw new Error("colorGradeAtTime: empty track");
  const keys = track.keys;
  if (tLocalMs <= keys[0]!.tMs) {
    const k = keys[0]!;
    return frameFromKey(k);
  }
  const last = keys[keys.length - 1]!;
  if (tLocalMs >= last.tMs) return frameFromKey(last);
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i]!;
    const b = keys[i + 1]!;
    if (tLocalMs >= a.tMs && tLocalMs <= b.tMs) {
      const t = (tLocalMs - a.tMs) / Math.max(1e-9, b.tMs - a.tMs);
      return {
        primary: lerpPrimary(a.primary, b.primary, t),
        secondaries: t < 0.5 ? a.secondaries ?? [] : b.secondaries ?? [],
        lutId: t < 0.5 ? a.lutId ?? null : b.lutId ?? null,
        lutStrength: lerp(a.lutStrength ?? 1, b.lutStrength ?? 1, t),
      };
    }
  }
  return frameFromKey(last);
}

function frameFromKey(k: ColorGradeKey): ColorGradeFrame {
  return {
    primary: k.primary,
    secondaries: k.secondaries ?? [],
    lutId: k.lutId ?? null,
    lutStrength: k.lutStrength ?? 1,
  };
}

/* ====================================================================== */
/* RGB transforms (CPU reference impl + smoke tests)                      */
/* ====================================================================== */

/** Apply primary correction to an RGB triplet in [0..1]. Pure. */
export function applyPrimaryRgb(
  rgb: [number, number, number],
  p: ColorPrimary,
): [number, number, number] {
  const lift = p.lift ?? [0, 0, 0];
  const gamma = p.gamma ?? [1, 1, 1];
  const gain = p.gain ?? [1, 1, 1];
  const sat = p.saturation ?? 1;
  const contrast = p.contrast ?? 1;

  let r = applyLGG(rgb[0], lift[0], gamma[0], gain[0]);
  let g = applyLGG(rgb[1], lift[1], gamma[1], gain[1]);
  let b = applyLGG(rgb[2], lift[2], gamma[2], gain[2]);

  r = (r - 0.5) * contrast + 0.5;
  g = (g - 0.5) * contrast + 0.5;
  b = (b - 0.5) * contrast + 0.5;

  const Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  r = Y + (r - Y) * sat;
  g = Y + (g - Y) * sat;
  b = Y + (b - Y) * sat;

  const temp = (p.temperature ?? 0) / 100;
  const tint = (p.tint ?? 0) / 100;
  r += temp * 0.05;
  b -= temp * 0.05;
  g -= tint * 0.04;

  return [clamp01(r), clamp01(g), clamp01(b)];
}

function applyLGG(x: number, lift: number, gamma: number, gain: number): number {
  let v = (x + lift) * gain;
  if (v <= 0) return 0;
  const g = gamma <= 0 ? 1 : gamma;
  return Math.pow(v, 1 / g);
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

/* ----- HSL qualifier weight ------------------------------------------ */

export function rgbToHsl(rgb: [number, number, number]): [number, number, number] {
  const [r, g, b] = rgb;
  const mx = Math.max(r, g, b);
  const mn = Math.min(r, g, b);
  const l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l];
  const d = mx - mn;
  const s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  let h: number;
  switch (mx) {
    case r:
      h = ((g - b) / d + (g < b ? 6 : 0)) * 60;
      break;
    case g:
      h = ((b - r) / d + 2) * 60;
      break;
    default:
      h = ((r - g) / d + 4) * 60;
      break;
  }
  return [h, s, l];
}

/** Smoothstep [0..1]. */
function smoothstep(edge0: number, edge1: number, x: number): number {
  if (edge0 >= edge1) return x >= edge1 ? 1 : 0;
  const t = clamp01((x - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
}

/**
 * Score of how much an RGB pixel falls inside an HSL qualifier in [0..1].
 * Hue distance is wrapped (0 and 360 are the same).
 */
export function hslQualifierWeight(
  rgb: [number, number, number],
  q: HslQualifier,
): number {
  const [h, s, l] = rgbToHsl(rgb);
  const halfWidth = q.hueWidth / 2;
  let hueDist = Math.abs(((h - q.hueCenter + 540) % 360) - 180);
  hueDist = Math.min(hueDist, Math.abs(((q.hueCenter - h + 540) % 360) - 180));
  const fade = halfWidth * q.softness;
  const hueWeight =
    1 - smoothstep(halfWidth - fade, halfWidth + fade, hueDist);
  const [s0, s1] = q.saturationRange;
  const sFade = (s1 - s0) * q.softness * 0.5;
  const satWeight =
    smoothstep(s0 - sFade, s0 + sFade, s) *
    (1 - smoothstep(s1 - sFade, s1 + sFade, s));
  const [l0, l1] = q.luminanceRange;
  const lFade = (l1 - l0) * q.softness * 0.5;
  const lumWeight =
    smoothstep(l0 - lFade, l0 + lFade, l) *
    (1 - smoothstep(l1 - lFade, l1 + lFade, l));
  return hueWeight * satWeight * lumWeight;
}

/* ----- Power window weight ------------------------------------------- */

/**
 * Soft-edge gate weight for a power window at normalized pixel coords (u,v) ∈ [0..1].
 * Returns ∈ [0..1]; for `subtract`-style use, multiply by `(1 - weight)`.
 *
 * Supports ellipse + rect (with optional cornerRadius). For bezier_path we
 * fall back to a hard inside/outside test (point-in-polygon via segment
 * sampling) — feathering is approximate. Production path uses an SDF in the
 * shader; this CPU helper exists for testability.
 */
export function powerWindowWeight(
  u: number,
  v: number,
  w: PowerWindow,
): number {
  const inv = w.invert ? 1 : 0;
  const soft = Math.max(1e-4, w.softness);
  switch (w.shape.kind) {
    case "ellipse": {
      const dx = (u - w.shape.cx) / Math.max(1e-6, w.shape.rx);
      const dy = (v - w.shape.cy) / Math.max(1e-6, w.shape.ry);
      const r = Math.sqrt(dx * dx + dy * dy);
      const inside = 1 - smoothstep(1 - soft, 1 + soft, r);
      return Math.abs(inv - inside);
    }
    case "rect": {
      const rs = w.shape;
      const dxL = u - rs.left;
      const dxR = rs.right - u;
      const dyT = v - rs.top;
      const dyB = rs.bottom - v;
      const d = Math.min(dxL, dxR, dyT, dyB);
      const inside = smoothstep(-soft, soft, d);
      return Math.abs(inv - inside);
    }
    case "bezier_path": {
      const verts: Array<[number, number]> = [];
      for (const seg of w.shape.segments) {
        for (let i = 0; i < seg.points.length; i += 2) {
          const x = seg.points[i];
          const y = seg.points[i + 1];
          if (typeof x === "number" && typeof y === "number") {
            verts.push([x, y]);
          }
        }
      }
      if (verts.length < 3) return inv ? 1 : 0;
      let inside = false;
      for (let i = 0, j = verts.length - 1; i < verts.length; j = i++) {
        const [xi, yi] = verts[i]!;
        const [xj, yj] = verts[j]!;
        if (
          yi > v !== yj > v &&
          u < ((xj - xi) * (v - yi)) / (yj - yi + 1e-9) + xi
        ) {
          inside = !inside;
        }
      }
      return Math.abs(inv - (inside ? 1 : 0));
    }
  }
}
