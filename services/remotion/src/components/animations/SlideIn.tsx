import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export type SlideDirection = "left" | "right" | "up" | "down";

export interface SlideInProps {
  direction?: SlideDirection;
  distance?: number;
  durationInFrames?: number;
  delay?: number;
  ease?: EaseName;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const SlideIn: React.FC<SlideInProps> = ({
  direction = "up",
  distance = 80,
  durationInFrames = 18,
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
  const inv = 1 - p;
  const axis = direction === "left" || direction === "right" ? "X" : "Y";
  const sign = direction === "left" || direction === "up" ? -1 : 1;
  return (
    <div
      style={{
        opacity: p,
        transform: `translate${axis}(${inv * distance * sign}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
