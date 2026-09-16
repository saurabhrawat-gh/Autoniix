import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export interface BlurInProps {
  durationInFrames?: number;
  delay?: number;
  ease?: EaseName;
  fromBlurPx?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const BlurIn: React.FC<BlurInProps> = ({
  durationInFrames = 18,
  delay = 0,
  ease = "power2",
  fromBlurPx = 24,
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
  return (
    <div
      style={{
        filter: `blur(${(1 - p) * fromBlurPx}px)`,
        opacity: p,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
