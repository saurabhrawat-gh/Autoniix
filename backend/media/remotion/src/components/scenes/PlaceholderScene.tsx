import React from "react";
import { AbsoluteFill } from "remotion";

export interface PlaceholderSceneProps {
  label?: string;
  bg?: string;
  fg?: string;
}

/**
 * Phase 0 default scene. Renders a solid color with a label so any unknown
 * or unregistered scene_preset still produces a visible, valid frame.
 */
export const PlaceholderScene: React.FC<PlaceholderSceneProps> = ({
  label = "scene",
  bg = "#0A0A0A",
  fg = "#FFFFFF",
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        color: fg,
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 48,
        fontWeight: 700,
        letterSpacing: -1,
      }}
    >
      {label}
    </AbsoluteFill>
  );
};
