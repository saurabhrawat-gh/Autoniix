import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface BouncePopProps {
  delay?: number;
  damping?: number;
  mass?: number;
  stiffness?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const BouncePop: React.FC<BouncePopProps> = ({
  delay = 0,
  damping = 10,
  mass = 0.5,
  stiffness = 120,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({
    frame: frame - delay,
    fps,
    config: { damping, mass, stiffness },
    from: 0,
    to: 1,
  });
  return <div style={{ transform: `scale(${scale})`, ...style }}>{children}</div>;
};
