import React from "react";
import { AbsoluteFill } from "remotion";
import { ScaleIn } from "../animations/ScaleIn";

export interface FullScreenTextProps {
  text: string;
  bg?: string;
  color?: string;
  font?: string;
  weight?: number;
  size?: number;
  uppercase?: boolean;
}

export const FullScreenText: React.FC<FullScreenTextProps> = ({
  text,
  bg = "#000000",
  color = "#FFFFFF",
  font = "Inter, system-ui, sans-serif",
  weight = 900,
  size = 180,
  uppercase = true,
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        padding: 80,
      }}
    >
      <ScaleIn from={0.85} durationInFrames={18}>
        <div
          style={{
            color,
            fontFamily: font,
            fontWeight: weight,
            fontSize: size,
            lineHeight: 1,
            letterSpacing: -3,
            textAlign: "center",
            textTransform: uppercase ? "uppercase" : "none",
            maxWidth: "90%",
          }}
        >
          {text}
        </div>
      </ScaleIn>
    </AbsoluteFill>
  );
};
