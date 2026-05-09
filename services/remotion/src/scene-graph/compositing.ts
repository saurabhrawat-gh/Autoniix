/**
 * Phase 1A — Per-layer compositing helpers.
 *
 * Single source of truth for:
 *   1. Validation of `Compositing` values (blend mode + opacity).
 *   2. Mapping our IR `BlendMode` to CSS `mix-blend-mode` strings.
 *   3. Identifying modes that need a WebGL fallback (no CSS equivalent).
 *
 * The renderer imports `cssBlendMode()` and `requiresShader()` to decide
 * between the CSS fast path and the shader composite path.
 *
 * Design notes:
 *   - `add` and `subtract` are NOT in the CSS spec; we render those via a
 *     fragment shader on the Tier-1 (Chromium) worker today and a real WebGPU
 *     compositor in the future Tier-0 worker.
 *   - All other modes round-trip exactly through CSS `mix-blend-mode` on
 *     Chromium 99+, which matches our Remotion runtime.
 */

import { BLEND_MODES, type BlendMode, type Compositing } from "./types";

/* ------------------------------------------------------------------ */
/* Validation                                                          */
/* ------------------------------------------------------------------ */

const BLEND_SET: ReadonlySet<BlendMode> = new Set(BLEND_MODES);

export function isBlendMode(v: unknown): v is BlendMode {
  return typeof v === "string" && BLEND_SET.has(v as BlendMode);
}

/**
 * Validates a `Compositing` value. Throws on bad input; returns the
 * normalized value otherwise. Caller is responsible for storing the result.
 */
export function validateCompositing(c: Compositing, clipId: string): Compositing {
  if (c.blendMode !== undefined && !isBlendMode(c.blendMode)) {
    throw new Error(
      `compositing(${clipId}): unknown blendMode ${JSON.stringify(c.blendMode)}`,
    );
  }
  if (c.opacity !== undefined) {
    if (typeof c.opacity !== "number" || !Number.isFinite(c.opacity)) {
      throw new Error(`compositing(${clipId}): opacity must be a finite number`);
    }
    if (c.opacity < 0 || c.opacity > 1) {
      throw new Error(
        `compositing(${clipId}): opacity ${c.opacity} out of [0,1] range`,
      );
    }
  }
  return c;
}

/* ------------------------------------------------------------------ */
/* CSS mapping                                                         */
/* ------------------------------------------------------------------ */

/**
 * Maps an IR `BlendMode` to a CSS `mix-blend-mode` string, or `null` for modes
 * that need shader-based compositing.
 */
export function cssBlendMode(mode: BlendMode | undefined): string | null {
  switch (mode) {
    case undefined:
    case "normal":
      return "normal";
    case "multiply":
    case "screen":
    case "overlay":
    case "hard_light":
    case "color_dodge":
    case "color_burn":
    case "difference":
    case "exclusion":
    case "hue":
    case "saturation":
    case "color":
    case "luminosity":
      return mode.replace("_", "-"); // hard_light -> hard-light, etc.
    case "soft_light":
      return "soft-light";
    case "add":
    case "subtract":
      // No CSS equivalent — caller must use the shader path.
      return null;
    default: {
      // exhaustiveness check
      const _exhaustive: never = mode;
      void _exhaustive;
      return null;
    }
  }
}

/**
 * True if the mode requires the WebGL/WebGPU shader composite path
 * (i.e. has no `mix-blend-mode` equivalent).
 */
export function requiresShader(mode: BlendMode | undefined): boolean {
  return mode === "add" || mode === "subtract";
}

/* ------------------------------------------------------------------ */
/* Effective values                                                    */
/* ------------------------------------------------------------------ */

/** Returns the effective blend mode (default "normal") for any clip. */
export function effectiveBlendMode(c: Compositing | undefined): BlendMode {
  return c?.blendMode ?? "normal";
}

/** Returns the effective opacity (default 1.0) for any clip. */
export function effectiveOpacity(c: Compositing | undefined): number {
  return c?.opacity ?? 1.0;
}

/**
 * Resolves a CSS style chunk for a compositing value. Useful for the
 * renderer's `<BlendLayer>` wrapper.
 *
 * Returns `null` when the mode requires the shader path (caller decides).
 */
export function compositingToCss(c: Compositing | undefined): {
  mixBlendMode: string;
  opacity: number;
} | null {
  const mode = effectiveBlendMode(c);
  const css = cssBlendMode(mode);
  if (css === null) return null;
  return { mixBlendMode: css, opacity: effectiveOpacity(c) };
}
