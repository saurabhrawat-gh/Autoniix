import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import {
  computePathFollow,
  type BezierPath,
} from "../../registry/textAnimations";

/**
 * Phase 1B — Text glyphs aligned along a Bezier path.
 *
 * The path is in SVG user-space units (pixels relative to the wrapping SVG).
 * Animation comes from `spreadFrom`/`spreadTo` interpolated over the clip's
 * duration — text "uncoils" along the path.
 *
 * For static (non-animated) text along a path, set `spreadFrom = spreadTo = 1`.
 */
export interface PathFollowProps {
  text: string;
  path: BezierPath;
  /** SVG viewBox dimensions. */
  viewBoxPx: [number, number];
  /** Text-spread at clip start (0..1). Default 0 (chars stacked at start). */
  spreadFrom?: number;
  /** Text-spread at clip end (0..1). Default 1. */
  spreadTo?: number;
  /** Animation duration in frames. Default 30. */
  durationInFrames?: number;
  delayInFrames?: number;
  alignToPath?: boolean;
  fontSizePx?: number;
  fillColor?: string;
  fontFamily?: string;
  fontWeight?: number;
  style?: React.CSSProperties;
}

export const PathFollow: React.FC<PathFollowProps> = ({
  text,
  path,
  viewBoxPx,
  spreadFrom = 0,
  spreadTo = 1,
  durationInFrames = 30,
  delayInFrames = 0,
  alignToPath = true,
  fontSizePx = 28,
  fillColor = "currentColor",
  fontFamily,
  fontWeight = 600,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  void fps;
  const localFrame = Math.max(0, frame - delayInFrames);
  const t = Math.min(1, localFrame / Math.max(1, durationInFrames));
  const spread = spreadFrom + (spreadTo - spreadFrom) * t;
  const tLocalMs = (localFrame / 60) * 1000;

  const glyphs = computePathFollow(
    { text, path, spread, alignToPath },
    tLocalMs,
  );

  return (
    <svg
      viewBox={`0 0 ${viewBoxPx[0]} ${viewBoxPx[1]}`}
      width="100%"
      height="100%"
      style={style}
      xmlns="http://www.w3.org/2000/svg"
    >
      {glyphs.map((g, i) => (
        <text
          key={i}
          x={g.x}
          y={g.y}
          transform={`rotate(${(g.rotationRad * 180) / Math.PI}, ${g.x}, ${g.y})`}
          fontSize={fontSizePx}
          fill={fillColor}
          fontFamily={fontFamily}
          fontWeight={fontWeight}
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {g.char}
        </text>
      ))}
    </svg>
  );
};
