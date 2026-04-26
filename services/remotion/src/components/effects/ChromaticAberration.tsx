import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * RGB channel split via SVG feColorMatrix + feOffset. Pure-CSS approximation:
 * three copies with mix-blend-mode `screen` and small horizontal offsets. Cheap
 * but convincing. For higher quality, Phase 3 will add a WebGL shader variant.
 */
export interface ChromaticAberrationProps {
  strengthPx?: number;
  children?: React.ReactNode;
}

export const ChromaticAberration: React.FC<ChromaticAberrationProps> = ({
  strengthPx = 4,
  children,
}) => {
  if (!children) {
    // Overlay mode — render a faint RGB-split vignette around edges via gradient
    return (
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: `radial-gradient(ellipse at center,
            rgba(0,0,0,0) 55%,
            rgba(255,0,0,0.08) 80%,
            rgba(0,0,255,0.08) 100%)`,
        }}
      />
    );
  }
  const copy = (color: string, dx: number): React.CSSProperties => ({
    position: "absolute",
    inset: 0,
    filter: `drop-shadow(${dx}px 0 0 ${color})`,
    mixBlendMode: "screen",
    transform: `translateX(${dx * 0.5}px)`,
  });
  return (
    <AbsoluteFill>
      <div style={copy("#ff0040", -strengthPx)}>{children}</div>
      <div style={copy("#00ff80", 0)}>{children}</div>
      <div style={copy("#0080ff", strengthPx)}>{children}</div>
    </AbsoluteFill>
  );
};
