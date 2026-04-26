import React from "react";
import { AbsoluteFill, Img } from "remotion";

/**
 * Persistent channel-logo bug in a corner. Like Watermark but opinionated
 * for always-on channel branding (smaller, always 10-20% from corner).
 */
export type BugCorner = "tl" | "tr" | "bl" | "br";

export interface LogoBugProps {
  src: string;
  corner?: BugCorner;
  heightPx?: number;
  opacity?: number;
  padding?: number;
}

export const LogoBug: React.FC<LogoBugProps> = ({
  src,
  corner = "tr",
  heightPx = 60,
  opacity = 0.8,
  padding = 40,
}) => {
  const pos: React.CSSProperties = {};
  if (corner.includes("t")) pos.top = padding;
  else pos.bottom = padding;
  if (corner.includes("l")) pos.left = padding;
  else pos.right = padding;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", ...pos, opacity }}>
        <Img src={src} style={{ height: heightPx, width: "auto" }} />
      </div>
    </AbsoluteFill>
  );
};
