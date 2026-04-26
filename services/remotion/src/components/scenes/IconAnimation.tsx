import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { ScaleIn } from "../animations/ScaleIn";
import { FadeIn } from "../animations/FadeIn";
import { Pulse } from "../animations/Pulse";

export interface IconAnimationProps {
  iconUrl: string;
  label?: string;
  style?: "pop" | "pulse" | "rotate";
  bg?: string;
  color?: string;
  accent?: string;
  iconSize?: number;
}

export const IconAnimation: React.FC<IconAnimationProps> = ({
  iconUrl,
  label,
  style = "pop",
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
  iconSize = 400,
}) => {
  const iconEl = <Img src={iconUrl} style={{ width: iconSize, height: iconSize, objectFit: "contain" }} />;

  let animated: React.ReactNode;
  if (style === "pop") {
    animated = (
      <ScaleIn from={0} overshoot={0.2} durationInFrames={16} ease="back">
        {iconEl}
      </ScaleIn>
    );
  } else if (style === "pulse") {
    animated = (
      <ScaleIn from={0.3} overshoot={0.1} durationInFrames={14}>
        <Pulse bpm={90} amplitude={0.06}>
          {iconEl}
        </Pulse>
      </ScaleIn>
    );
  } else {
    animated = (
      <ScaleIn from={0} overshoot={0.1} durationInFrames={18}>
        <div
          style={{
            animation: "spin 8s linear infinite",
            // Note: CSS animations run during render because Remotion freezes the clock
            // based on frame time. For deterministic rotation, use useCurrentFrame.
          }}
        >
          {iconEl}
        </div>
      </ScaleIn>
    );
  }

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: 48,
      }}
    >
      <div
        style={{
          width: iconSize + 80,
          height: iconSize + 80,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}30 0%, transparent 70%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {animated}
      </div>
      {label && (
        <FadeIn durationInFrames={20} delay={10}>
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 900,
              fontSize: 72,
              color,
              letterSpacing: -1,
              textAlign: "center",
            }}
          >
            {label}
          </div>
        </FadeIn>
      )}
    </AbsoluteFill>
  );
};
