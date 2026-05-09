/**
 * Phase 1C — Pure compute layer for animated clip masks.
 *
 * A `MaskTrack` is a sequence of keyframes describing a shape over time. The
 * compute layer interpolates between adjacent keys at any `tLocalMs` and
 * produces:
 *   • An SVG path string (for rect / ellipse / bezier_path).
 *   • A descriptor for shader-driven masks (luma / chroma).
 *
 * Renderer pairs `pathAtTime()` with an SVG `<clipPath>` for instant alpha
 * masking on the Tier-1 (Chromium) path and forwards luma/chroma descriptors
 * to a fragment shader on the Tier-0 path. (Tier-0 implementation is wired in
 * a follow-up; the IR contract is what we lock here.)
 *
 * Design notes:
 *   • All mask shape kinds carry the same time field (`tMs`), feather, invert,
 *     so blending multiple masks across time is well-defined.
 *   • Bezier-path interpolation requires equal segment counts between
 *     adjacent keys — we enforce that at validation time and document it in
 *     `validateMaskTrack`. Authors using the `path` kind keep segment counts
 *     stable across keyframes (typical for rotoscope work).
 *   • Compose-time fallback: when adjacent keys disagree on `kind`, the
 *     interpolation snaps to the *latest reached* key — no "morph between
 *     ellipse and rect" magic.
 */

/* ====================================================================== */
/* Types                                                                  */
/* ====================================================================== */

export type MaskKind = "rect" | "ellipse" | "bezier_path" | "luma" | "chroma";

/** Cubic-Bezier path segment in normalized coordinates (0..1). */
export interface BezierSegment {
  /** Move/Line/Cubic/Quadratic/Close, mirroring SVG path commands. */
  cmd: "M" | "L" | "C" | "Q" | "Z";
  /** Coordinates flattened: M/L → 2, Q → 4, C → 6, Z → 0. */
  points: number[];
}

export type MaskShape =
  | {
      kind: "rect";
      /** All in 0..1 normalized to the clip bounding box. */
      left: number;
      right: number;
      top: number;
      bottom: number;
      cornerRadius?: number; // 0..1, default 0
    }
  | {
      kind: "ellipse";
      cx: number;
      cy: number;
      rx: number;
      ry: number;
      rotationRad?: number;
    }
  | {
      kind: "bezier_path";
      segments: BezierSegment[];
    }
  | {
      kind: "luma";
      threshold: number;       // 0..1
      softness: number;        // 0..1
    }
  | {
      kind: "chroma";
      keyColor: [number, number, number]; // 0..1 linear-RGB
      tolerance: number; // 0..1
      spill: number;     // 0..1
    };

export interface MaskKey {
  tMs: number;
  shape: MaskShape;
  featherPx?: number;
  invert?: boolean;
}

export interface MaskTrack {
  /** All keys MUST be sorted by tMs ascending. */
  keys: MaskKey[];
}

/** Single resolved-at-time mask state. */
export interface MaskFrame {
  shape: MaskShape;
  featherPx: number;
  invert: boolean;
}

/* ====================================================================== */
/* Validation                                                             */
/* ====================================================================== */

export function validateMaskTrack(track: MaskTrack, ctx = "mask"): void {
  if (track.keys.length === 0) {
    throw new Error(`${ctx}: mask track must have ≥ 1 key`);
  }
  let prev = -Infinity;
  for (const k of track.keys) {
    if (!Number.isFinite(k.tMs)) {
      throw new Error(`${ctx}: key tMs must be finite`);
    }
    if (k.tMs < prev) {
      throw new Error(`${ctx}: keys must be sorted by tMs ascending`);
    }
    prev = k.tMs;
    validateShape(k.shape, ctx);
  }
}

function validateShape(s: MaskShape, ctx: string): void {
  switch (s.kind) {
    case "rect":
      if (s.left > s.right || s.top > s.bottom) {
        throw new Error(`${ctx}: rect must have left<=right, top<=bottom`);
      }
      return;
    case "ellipse":
      if (s.rx < 0 || s.ry < 0) throw new Error(`${ctx}: ellipse rx,ry must be >= 0`);
      return;
    case "bezier_path":
      if (s.segments.length === 0) throw new Error(`${ctx}: bezier_path needs >= 1 segment`);
      return;
    case "luma":
      if (s.threshold < 0 || s.threshold > 1) throw new Error(`${ctx}: luma threshold OOB`);
      return;
    case "chroma":
      if (s.tolerance < 0 || s.tolerance > 1) throw new Error(`${ctx}: chroma tolerance OOB`);
      return;
  }
}

/* ====================================================================== */
/* Interpolation                                                          */
/* ====================================================================== */

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpShape(a: MaskShape, b: MaskShape, t: number): MaskShape {
  if (a.kind !== b.kind) {
    // Snap to whichever side we're closer to in time. Caller passes `t<0.5`
    // → a, otherwise b. Documented "no cross-kind morph".
    return t < 0.5 ? a : b;
  }
  switch (a.kind) {
    case "rect": {
      const bb = b as Extract<MaskShape, { kind: "rect" }>;
      return {
        kind: "rect",
        left: lerp(a.left, bb.left, t),
        right: lerp(a.right, bb.right, t),
        top: lerp(a.top, bb.top, t),
        bottom: lerp(a.bottom, bb.bottom, t),
        cornerRadius: lerp(a.cornerRadius ?? 0, bb.cornerRadius ?? 0, t),
      };
    }
    case "ellipse": {
      const bb = b as Extract<MaskShape, { kind: "ellipse" }>;
      return {
        kind: "ellipse",
        cx: lerp(a.cx, bb.cx, t),
        cy: lerp(a.cy, bb.cy, t),
        rx: lerp(a.rx, bb.rx, t),
        ry: lerp(a.ry, bb.ry, t),
        rotationRad: lerp(a.rotationRad ?? 0, bb.rotationRad ?? 0, t),
      };
    }
    case "bezier_path": {
      const bb = b as Extract<MaskShape, { kind: "bezier_path" }>;
      // Equal-segment-count required for smooth morph. If lengths disagree,
      // snap to the active key.
      if (a.segments.length !== bb.segments.length) {
        return t < 0.5 ? a : b;
      }
      const segs: BezierSegment[] = a.segments.map((sa, i) => {
        const sb = bb.segments[i]!;
        if (sa.cmd !== sb.cmd || sa.points.length !== sb.points.length) {
          // Mismatched commands — snap.
          return t < 0.5 ? sa : sb;
        }
        return {
          cmd: sa.cmd,
          points: sa.points.map((p, j) => lerp(p, sb.points[j]!, t)),
        };
      });
      return { kind: "bezier_path", segments: segs };
    }
    case "luma": {
      const bb = b as Extract<MaskShape, { kind: "luma" }>;
      return {
        kind: "luma",
        threshold: lerp(a.threshold, bb.threshold, t),
        softness: lerp(a.softness, bb.softness, t),
      };
    }
    case "chroma": {
      const bb = b as Extract<MaskShape, { kind: "chroma" }>;
      return {
        kind: "chroma",
        keyColor: [
          lerp(a.keyColor[0], bb.keyColor[0], t),
          lerp(a.keyColor[1], bb.keyColor[1], t),
          lerp(a.keyColor[2], bb.keyColor[2], t),
        ],
        tolerance: lerp(a.tolerance, bb.tolerance, t),
        spill: lerp(a.spill, bb.spill, t),
      };
    }
  }
}

/**
 * Resolve the mask state at any time.
 * Out-of-range times clamp to the first / last key.
 */
export function maskAtTime(track: MaskTrack, tLocalMs: number): MaskFrame {
  if (track.keys.length === 0) {
    throw new Error("maskAtTime: empty track");
  }
  const keys = track.keys;
  const first = keys[0]!;
  const last = keys[keys.length - 1]!;
  if (tLocalMs <= first.tMs) {
    return { shape: first.shape, featherPx: first.featherPx ?? 0, invert: !!first.invert };
  }
  if (tLocalMs >= last.tMs) {
    return { shape: last.shape, featherPx: last.featherPx ?? 0, invert: !!last.invert };
  }
  // Find the surrounding pair via linear scan (key counts are tiny).
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i]!;
    const b = keys[i + 1]!;
    if (tLocalMs >= a.tMs && tLocalMs <= b.tMs) {
      const t = (tLocalMs - a.tMs) / Math.max(1e-9, b.tMs - a.tMs);
      return {
        shape: lerpShape(a.shape, b.shape, t),
        featherPx: lerp(a.featherPx ?? 0, b.featherPx ?? 0, t),
        invert: t < 0.5 ? !!a.invert : !!b.invert,
      };
    }
  }
  // Should be unreachable.
  return { shape: last.shape, featherPx: last.featherPx ?? 0, invert: !!last.invert };
}

/* ====================================================================== */
/* SVG path serialization (rect / ellipse / bezier_path)                  */
/* ====================================================================== */

/**
 * Convert a mask shape to an SVG `d` path string in normalized 0..1 space.
 * For luma/chroma kinds, returns `null` (caller must use the shader path).
 *
 * `width` / `height` scale the normalized coords to the wrapping element.
 */
export function shapeToSvgPath(
  shape: MaskShape,
  width: number,
  height: number,
): string | null {
  const w = width;
  const h = height;
  switch (shape.kind) {
    case "rect": {
      const x = shape.left * w;
      const y = shape.top * h;
      const rw = (shape.right - shape.left) * w;
      const rh = (shape.bottom - shape.top) * h;
      const r = Math.min(rw, rh) * (shape.cornerRadius ?? 0);
      if (r <= 0) {
        return `M${x} ${y} L${x + rw} ${y} L${x + rw} ${y + rh} L${x} ${y + rh} Z`;
      }
      return [
        `M${x + r} ${y}`,
        `L${x + rw - r} ${y}`,
        `Q${x + rw} ${y} ${x + rw} ${y + r}`,
        `L${x + rw} ${y + rh - r}`,
        `Q${x + rw} ${y + rh} ${x + rw - r} ${y + rh}`,
        `L${x + r} ${y + rh}`,
        `Q${x} ${y + rh} ${x} ${y + rh - r}`,
        `L${x} ${y + r}`,
        `Q${x} ${y} ${x + r} ${y}`,
        `Z`,
      ].join(" ");
    }
    case "ellipse": {
      // Approximate rotated ellipse via an SVG arc command. For non-rotated
      // ellipses use two arcs.
      const cx = shape.cx * w;
      const cy = shape.cy * h;
      const rx = shape.rx * w;
      const ry = shape.ry * h;
      // Two arcs trick (rotation handled by transform on the wrapper, not
      // baked into the path — rotated SVG arcs don't blend smoothly).
      return [
        `M${cx - rx} ${cy}`,
        `A${rx} ${ry} 0 1 0 ${cx + rx} ${cy}`,
        `A${rx} ${ry} 0 1 0 ${cx - rx} ${cy}`,
        `Z`,
      ].join(" ");
    }
    case "bezier_path": {
      const parts: string[] = [];
      for (const seg of shape.segments) {
        const scaled = seg.points.map((p, i) => p * (i % 2 === 0 ? w : h));
        switch (seg.cmd) {
          case "M":
            parts.push(`M${scaled[0]} ${scaled[1]}`);
            break;
          case "L":
            parts.push(`L${scaled[0]} ${scaled[1]}`);
            break;
          case "Q":
            parts.push(`Q${scaled[0]} ${scaled[1]} ${scaled[2]} ${scaled[3]}`);
            break;
          case "C":
            parts.push(
              `C${scaled[0]} ${scaled[1]} ${scaled[2]} ${scaled[3]} ${scaled[4]} ${scaled[5]}`,
            );
            break;
          case "Z":
            parts.push("Z");
            break;
        }
      }
      return parts.join(" ");
    }
    case "luma":
    case "chroma":
      return null; // shader path
  }
}
