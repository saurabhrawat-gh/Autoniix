import React from "react";
import { AbsoluteFill } from "remotion";

export interface VignetteProps {
  intensity?: number;
  radius?: number;
  color?: string;
}

export const Vignette: React.FC<VignetteProps> = ({
  intensity = 0.55,
  radius = 0.55,
  color = "#000000",
}) => {
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(ellipse at center, rgba(0,0,0,0) ${
          radius * 100
        }%, ${color} 100%)`,
        opacity: intensity,
      }}
    />
  );
};
