import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

export interface TypewriterProps {
  text: string;
  cps?: number; // characters per second
  delay?: number; // frames
  cursor?: boolean;
  style?: React.CSSProperties;
}

export const Typewriter: React.FC<TypewriterProps> = ({
  text,
  cps = 30,
  delay = 0,
  cursor = true,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const elapsedSec = Math.max(0, (frame - delay) / fps);
  const chars = Math.min(text.length, Math.floor(elapsedSec * cps));
  const showCursor = cursor && Math.floor(frame / (fps / 2)) % 2 === 0;

  return (
    <span style={style}>
      {text.slice(0, chars)}
      {showCursor && <span style={{ opacity: 0.75 }}>▍</span>}
    </span>
  );
};
