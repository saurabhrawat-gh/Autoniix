import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export type FlipAxis = "x" | "y";

export interface FlipInProps {
  axis?: FlipAxis;
  durationInFrames?: number;
  delay?: number;
  ease?: EaseName;
  perspective?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const FlipIn: React.FC<FlipInProps> = ({
  axis = "y",
  durationInFrames = 18,
  delay = 0,
  ease = "back",
  perspective = 1200,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const p = easings[ease](
    interpolate(frame - delay, [0, durationInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const angle = (1 - p) * 90;
  const rot = axis === "y" ? `rotateY(${angle}deg)` : `rotateX(${-angle}deg)`;
  return (
    <div style={{ perspective, ...style }}>
      <div
        style={{
          transform: rot,
          opacity: p,
          transformStyle: "preserve-3d",
          backfaceVisibility: "hidden",
        }}
      >
        {children}
      </div>
    </div>
  );
};
