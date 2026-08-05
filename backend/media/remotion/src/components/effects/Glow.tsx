import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Edge-glow / inner-glow vignette. Use as a top-stacked overlay.
 */
export interface GlowProps {
  color?: string;
  intensity?: number;
  spreadPct?: number;
}

export const Glow: React.FC<GlowProps> = ({
  color = "#FFD60A",
  intensity = 0.5,
  spreadPct = 40,
}) => {
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        boxShadow: `inset 0 0 ${spreadPct * 4}px ${color}`,
        opacity: intensity,
        mixBlendMode: "screen",
      }}
    />
  );
};
