import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { ScaleIn } from "../animations/ScaleIn";

export interface IntroAnimationProps {
  channelName: string;
  logoUrl?: string;
  tagline?: string;
  bg?: string;
  color?: string;
  accent?: string;
}

export const IntroAnimation: React.FC<IntroAnimationProps> = ({
  channelName,
  logoUrl,
  tagline,
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const sweepX = interpolate(
    frame,
    [Math.round(durationInFrames * 0.35), Math.round(durationInFrames * 0.55)],
    [-100, 120],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeOut,
      }}
    >
      <ScaleIn from={0.4} overshoot={0.12} durationInFrames={18} ease="back">
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          {logoUrl && <Img src={logoUrl} style={{ height: 140 }} />}
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 900,
              fontSize: 140,
              color,
              letterSpacing: -3,
            }}
          >
            {channelName}
          </div>
        </div>
      </ScaleIn>
      {tagline && (
        <div
          style={{
            marginTop: 32,
            fontFamily: "Inter, sans-serif",
            fontWeight: 500,
            fontSize: 36,
            color: accent,
            letterSpacing: 3,
            textTransform: "uppercase",
          }}
        >
          {tagline}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          width: "20%",
          left: `${sweepX}%`,
          background: `linear-gradient(90deg, transparent, ${accent}80, transparent)`,
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
