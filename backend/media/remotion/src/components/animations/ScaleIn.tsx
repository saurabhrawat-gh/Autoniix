import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export interface ScaleInProps {
  from?: number;
  overshoot?: number;
  durationInFrames?: number;
  delay?: number;
  ease?: EaseName;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const ScaleIn: React.FC<ScaleInProps> = ({
  from = 0.9,
  overshoot = 0,
  durationInFrames = 15,
  delay = 0,
  ease = "power3",
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
  const scale =
    overshoot > 0
      ? interpolate(p, [0, 0.6, 1], [from, 1 + overshoot, 1])
      : from + (1 - from) * p;

  return (
    <div style={{ opacity: p, transform: `scale(${scale})`, ...style }}>{children}</div>
  );
};
