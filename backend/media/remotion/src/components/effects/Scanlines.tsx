import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Pure-CSS scanlines overlay (no WebGL). Lighter weight than the full CRT
 * shader when the scene only needs a subtle broadcast-tube feel.
 */
export interface ScanlinesProps {
  lineHeight?: number;
  opacity?: number;
  color?: string;
}

export const Scanlines: React.FC<ScanlinesProps> = ({
  lineHeight = 3,
  opacity = 0.35,
  color = "#000000",
}) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      opacity,
      backgroundImage: `repeating-linear-gradient(
        to bottom,
        transparent 0px,
        transparent ${lineHeight - 1}px,
        ${color} ${lineHeight - 1}px,
        ${color} ${lineHeight}px
      )`,
    }}
  />
);
