import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Cinematic letterbox bars. `aspect` is the target aspect ratio (e.g. 2.35
 * for anamorphic), interpreted within the current composition frame.
 */
export interface LetterboxProps {
  aspect?: number;
  color?: string;
}

export const Letterbox: React.FC<LetterboxProps> = ({ aspect = 2.35, color = "#000" }) => {
  const base = 16 / 9;
  const ratio = aspect / base;
  const visibleFraction = ratio > 1 ? 1 / ratio : 1;
  const barPct = ((1 - visibleFraction) / 2) * 100;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: `${barPct}%`,
          background: color,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: `${barPct}%`,
          background: color,
        }}
      />
    </AbsoluteFill>
  );
};
