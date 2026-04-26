import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

export interface PulseProps {
  bpm?: number; // pulses per minute
  amplitude?: number; // scale delta (e.g. 0.05 → scales 1→1.05)
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const Pulse: React.FC<PulseProps> = ({
  bpm = 90,
  amplitude = 0.06,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const hz = bpm / 60;
  const scale = 1 + amplitude * Math.sin(2 * Math.PI * hz * (frame / fps));
  return <div style={{ transform: `scale(${scale})`, ...style }}>{children}</div>;
};
