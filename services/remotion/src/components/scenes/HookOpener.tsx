import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { ScaleIn } from "../animations/ScaleIn";
import { FadeIn } from "../animations/FadeIn";

export type HookStyle = "question" | "statement" | "stat";

export interface HookOpenerProps {
  text: string;
  subtitle?: string;
  style?: HookStyle;
  flash?: boolean;
  bg?: string;
  color?: string;
  accent?: string;
}

export const HookOpener: React.FC<HookOpenerProps> = ({
  text,
  subtitle,
  style = "question",
  flash = false,
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FF3B30",
}) => {
  const frame = useCurrentFrame();
  const flashOpacity = flash
    ? interpolate(frame, [0, 3, 6], [1, 0.4, 0], { extrapolateRight: "clamp" })
    : 0;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        padding: 100,
      }}
    >
      <ScaleIn from={0} overshoot={0.1} durationInFrames={12} ease="back">
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: style === "stat" ? 220 : 140,
            color,
            lineHeight: 1.05,
            letterSpacing: -3,
            textAlign: "center",
            maxWidth: "90%",
            textTransform: style === "statement" ? "uppercase" : "none",
          }}
        >
          {style === "question" && <span style={{ color: accent }}>?</span>}
          {text}
          {style === "question" && <span style={{ color: accent }}>?</span>}
        </div>
      </ScaleIn>
      {subtitle && (
        <div style={{ marginTop: 32 }}>
          <FadeIn durationInFrames={20} delay={10}>
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontWeight: 500,
                fontSize: 42,
                color,
                opacity: 0.75,
                textAlign: "center",
                letterSpacing: 1,
              }}
            >
              {subtitle}
            </div>
          </FadeIn>
        </div>
      )}

      {flash && (
        <AbsoluteFill
          style={{
            backgroundColor: "#fff",
            opacity: flashOpacity,
            pointerEvents: "none",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
