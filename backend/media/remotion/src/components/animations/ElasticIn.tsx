import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface ElasticInProps {
  delay?: number;
  overshootClamping?: boolean;
  damping?: number;
  mass?: number;
  stiffness?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const ElasticIn: React.FC<ElasticInProps> = ({
  delay = 0,
  overshootClamping = false,
  damping = 5,
  mass = 0.4,
  stiffness = 90,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping, mass, stiffness, overshootClamping },
    from: 0,
    to: 1,
  });
  return (
    <div style={{ transform: `scale(${s}) translateY(${(1 - s) * 20}px)`, opacity: Math.min(1, s + 0.2), ...style }}>
      {children}
    </div>
  );
};
