import React from "react";
import { random, useCurrentFrame } from "remotion";

export interface ShakeProps {
  intensity?: number;
  rotationDeg?: number;
  /** Triggers after `delay` frames, lasts `durationInFrames`, then settles. */
  delay?: number;
  durationInFrames?: number;
  seed?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const Shake: React.FC<ShakeProps> = ({
  intensity = 12,
  rotationDeg = 1.5,
  delay = 0,
  durationInFrames = 30,
  seed = "shake",
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const active = frame >= delay && frame < delay + durationInFrames;
  const falloff = active
    ? 1 - (frame - delay) / durationInFrames
    : 0;

  const dx = active ? (random(`${seed}-x-${frame}`) * 2 - 1) * intensity * falloff : 0;
  const dy = active ? (random(`${seed}-y-${frame}`) * 2 - 1) * intensity * falloff : 0;
  const rz = active
    ? (random(`${seed}-r-${frame}`) * 2 - 1) * rotationDeg * falloff
    : 0;

  return (
    <div
      style={{
        transform: `translate(${dx}px, ${dy}px) rotate(${rz}deg)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
