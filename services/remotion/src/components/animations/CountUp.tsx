import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { easings, type EaseName } from "../../utils/easing";

export interface CountUpProps {
  from?: number;
  to: number;
  durationInFrames?: number;
  delay?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  ease?: EaseName;
  style?: React.CSSProperties;
}

export const CountUp: React.FC<CountUpProps> = ({
  from = 0,
  to,
  durationInFrames = 60,
  delay = 0,
  decimals = 0,
  prefix = "",
  suffix = "",
  ease = "power2",
  style,
}) => {
  const frame = useCurrentFrame();
  const p = easings[ease](
    interpolate(frame - delay, [0, durationInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const value = from + (to - from) * p;
  return (
    <span style={style}>
      {prefix}
      {value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
};
