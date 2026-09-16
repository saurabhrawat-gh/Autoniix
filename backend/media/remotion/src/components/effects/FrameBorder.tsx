import React from "react";
import { AbsoluteFill } from "remotion";

export interface FrameBorderProps {
  color?: string;
  widthPx?: number;
  inset?: number;
  radius?: number;
  shadow?: boolean;
}

export const FrameBorder: React.FC<FrameBorderProps> = ({
  color = "#FFFFFF",
  widthPx = 8,
  inset = 36,
  radius = 0,
  shadow = true,
}) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: inset,
          left: inset,
          right: inset,
          bottom: inset,
          border: `${widthPx}px solid ${color}`,
          borderRadius: radius,
          boxShadow: shadow ? "0 0 40px rgba(0,0,0,0.5)" : "none",
        }}
      />
    </AbsoluteFill>
  );
};
