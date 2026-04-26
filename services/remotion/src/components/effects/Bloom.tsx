import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Cheap bloom via a blurred, brightness-boosted copy composited as `screen`.
 * Accepts children (wraps them) — use as a CSS-filter style effect.
 */
export interface BloomProps {
  intensity?: number; // 0..1
  blurPx?: number;
  children?: React.ReactNode;
}

export const Bloom: React.FC<BloomProps> = ({ intensity = 0.5, blurPx = 30, children }) => {
  if (!children) {
    // Standalone overlay: bright gradient in center
    return (
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: `radial-gradient(circle at 50% 50%, rgba(255,255,255,${intensity * 0.3}) 0%, rgba(255,255,255,0) 60%)`,
          mixBlendMode: "screen",
        }}
      />
    );
  }
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", inset: 0 }}>{children}</div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          filter: `blur(${blurPx}px) brightness(${1 + intensity})`,
          mixBlendMode: "screen",
          opacity: intensity,
          pointerEvents: "none",
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
