import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

export interface WaveTextProps {
  text: string;
  amplitudePx?: number;
  speed?: number; // cycles/sec
  wavelengthChars?: number; // how many chars fit in a full wave
  color?: string;
  style?: React.CSSProperties;
}

export const WaveText: React.FC<WaveTextProps> = ({
  text,
  amplitudePx = 14,
  speed = 1.2,
  wavelengthChars = 6,
  color,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  return (
    <span style={{ display: "inline-block", color, ...style }}>
      {Array.from(text).map((ch, i) => {
        if (ch === " ") return " ";
        const phase = (i / wavelengthChars) * 2 * Math.PI - speed * 2 * Math.PI * t;
        const y = Math.sin(phase) * amplitudePx;
        return (
          <span
            key={i}
            style={{ display: "inline-block", transform: `translateY(${y}px)` }}
          >
            {ch}
          </span>
        );
      })}
    </span>
  );
};
