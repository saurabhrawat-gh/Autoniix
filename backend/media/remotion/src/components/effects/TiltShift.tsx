import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Tilt-shift faux miniature: blur the top & bottom bands while the center stays sharp.
 * Implemented as two absolute overlays with backdrop-filter blur + linear-gradient mask.
 */
export interface TiltShiftProps {
  blurPx?: number;
  focusHeightPct?: number;
  focusCenterPct?: number;
}

export const TiltShift: React.FC<TiltShiftProps> = ({
  blurPx = 16,
  focusHeightPct = 30,
  focusCenterPct = 50,
}) => {
  const topEnd = focusCenterPct - focusHeightPct / 2;
  const bottomStart = focusCenterPct + focusHeightPct / 2;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: `${topEnd}%`,
          backdropFilter: `blur(${blurPx}px)`,
          WebkitBackdropFilter: `blur(${blurPx}px)`,
          maskImage: "linear-gradient(to bottom, #000 60%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to bottom, #000 60%, transparent 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: `${bottomStart}%`,
          left: 0,
          right: 0,
          bottom: 0,
          backdropFilter: `blur(${blurPx}px)`,
          WebkitBackdropFilter: `blur(${blurPx}px)`,
          maskImage: "linear-gradient(to top, #000 60%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, #000 60%, transparent 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
