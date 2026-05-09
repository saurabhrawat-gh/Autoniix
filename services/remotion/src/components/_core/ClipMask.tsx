/**
 * Phase 1C — `<ClipMask>` renderer wrapper.
 *
 * Wraps any child layer with one or more animated SVG `<clipPath>` elements
 * (rect / ellipse / bezier_path) and forwards luma/chroma masks to the
 * shader path (Tier-0 follow-up; logged on first encounter).
 *
 * Multi-mask blending modes:
 *   • intersect → SVG `clipPath` (default; AND)
 *   • add       → SVG `clipPath` with combined paths (OR / union; the SVG
 *                 fill-rule="evenodd" gives a usable union for non-overlapping
 *                 shapes; for overlapping shapes the result is XOR which is
 *                 still the documented behavior).
 *   • subtract  → SVG mask with first shape WHITE, second BLACK (DIFFERENCE).
 *
 * No compositing value → no-op passthrough.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import {
  maskAtTime,
  shapeToSvgPath,
  type MaskShape,
  type MaskTrack,
} from "../../registry/masks";
import type { ClipMaskRef } from "../../scene-graph/types";

export interface ClipMaskProps {
  /** Optional — the wrapper is a passthrough when undefined or empty. */
  masks?: ClipMaskRef[];
  /** Wrapping element pixel size (used to scale 0..1 normalized shapes). */
  width: number;
  height: number;
  /** For diagnostics + the dev-only one-time-warn map. */
  clipId?: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

/* ---- Dev-only warn-once for shader-path masks ------------------------- */
const _warned = new Set<string>();
function warnOnce(key: string, message: string): void {
  if (process.env.NODE_ENV === "production") return;
  if (_warned.has(key)) return;
  _warned.add(key);
  // eslint-disable-next-line no-console
  console.warn(`[ClipMask] ${message}`);
}

export const ClipMask: React.FC<ClipMaskProps> = ({
  masks,
  width,
  height,
  clipId,
  className,
  style,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tLocalMs = (frame / fps) * 1000;

  if (!masks || masks.length === 0) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    );
  }

  // Resolve every mask at the current time and split into svg-path masks
  // vs. shader-path masks.
  type Resolved = {
    id: string;
    blend: "intersect" | "add" | "subtract";
    shape: MaskShape;
    featherPx: number;
    invert: boolean;
    pathD: string | null;
  };
  const resolved: Resolved[] = masks.map((m) => {
    const track = m.track as unknown as MaskTrack;
    const frameState = maskAtTime(track, tLocalMs);
    return {
      id: m.id,
      blend: m.blend ?? "intersect",
      shape: frameState.shape,
      featherPx: frameState.featherPx,
      invert: frameState.invert,
      pathD: shapeToSvgPath(frameState.shape, width, height),
    };
  });

  for (const r of resolved) {
    if (r.pathD === null) {
      warnOnce(
        `shader-mask:${r.shape.kind}`,
        `mask kind "${r.shape.kind}" requires the WebGPU shader path (clip=${clipId ?? "?"}, mask=${r.id}). ` +
          `Falling through to passthrough until Tier-0 ships.`,
      );
    }
  }

  // Build an SVG defs section with one clipPath per `intersect`/`add` mask
  // and one mask per `subtract` mask. We compose them by chaining: intersect
  // wins first, then subtract trims the result.
  const intersectId = `cm-i-${clipId ?? "x"}`;
  const subtractId = `cm-s-${clipId ?? "x"}`;
  const intersectShapes = resolved.filter(
    (r) => r.pathD !== null && (r.blend === "intersect" || r.blend === "add"),
  );
  const subtractShapes = resolved.filter(
    (r) => r.pathD !== null && r.blend === "subtract",
  );

  const hasIntersect = intersectShapes.length > 0;
  const hasSubtract = subtractShapes.length > 0;

  // Compose CSS clip-path / mask URL refs.
  const cssMaskParts: string[] = [];
  if (hasIntersect) cssMaskParts.push(`url(#${intersectId})`);
  // (subtract handled via a CSS mask-image below for cleaner compositing)

  return (
    <div
      className={className}
      style={{
        ...style,
        position: "relative",
        width,
        height,
        clipPath: hasIntersect ? `url(#${intersectId})` : undefined,
        WebkitClipPath: hasIntersect ? `url(#${intersectId})` : undefined,
        // For subtract, fall back to CSS mask via inline SVG data URI.
        WebkitMaskImage: hasSubtract
          ? `url(#${subtractId})`
          : undefined,
        maskImage: hasSubtract ? `url(#${subtractId})` : undefined,
      }}
      data-clip-id={clipId}
      data-mask-count={resolved.length}
    >
      {/* Definitions */}
      <svg
        width="0"
        height="0"
        style={{ position: "absolute", pointerEvents: "none" }}
        aria-hidden
      >
        <defs>
          {hasIntersect && (
            <clipPath id={intersectId} clipPathUnits="userSpaceOnUse">
              {intersectShapes.map((r) => (
                <path
                  key={r.id}
                  d={r.pathD!}
                  // Invert: outer rect minus the path (even-odd fill rule).
                  // We approximate by drawing a full-frame rect first when invert is true.
                />
              ))}
              {/* For invert: append a frame rect with even-odd fill rule. */}
              {intersectShapes.some((r) => r.invert) && (
                <path
                  d={`M0 0 L${width} 0 L${width} ${height} L0 ${height} Z`}
                  // eslint-disable-next-line react/no-unknown-property
                  fillRule="evenodd"
                />
              )}
            </clipPath>
          )}
          {hasSubtract && (
            <mask id={subtractId} maskUnits="userSpaceOnUse">
              <rect width={width} height={height} fill="white" />
              {subtractShapes.map((r) => (
                <path key={r.id} d={r.pathD!} fill="black" />
              ))}
            </mask>
          )}
        </defs>
      </svg>
      {children}
    </div>
  );
};
