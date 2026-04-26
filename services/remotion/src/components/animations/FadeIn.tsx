import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export interface FadeInProps {
  durationInFrames?: number;
  delay?: number;
  ease?: EaseName;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const FadeIn: React.FC<FadeInProps> = ({
  durationInFrames = 15,
  delay = 0,
  ease = "power2",
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
  return <div style={{ opacity: p, ...style }}>{children}</div>;
};
