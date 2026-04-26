import React from "react";
import { AbsoluteFill } from "remotion";
import { SlideIn } from "../animations/SlideIn";

export type LowerThirdStyle = "news_red" | "minimal_white" | "gradient_modern";

export interface LowerThirdProps {
  title: string;
  subtitle?: string;
  style?: LowerThirdStyle;
  accent?: string;
  position?: "left" | "center" | "right";
}

export const LowerThird: React.FC<LowerThirdProps> = ({
  title,
  subtitle,
  style = "minimal_white",
  accent = "#FF3B30",
  position = "left",
}) => {
  const bg =
    style === "news_red"
      ? accent
      : style === "gradient_modern"
        ? "linear-gradient(90deg, rgba(0,0,0,0.85), rgba(0,0,0,0.1))"
        : "rgba(255,255,255,0.95)";
  const color = style === "minimal_white" ? "#0A0A0A" : "#FFFFFF";
  const justify =
    position === "center" ? "center" : position === "right" ? "flex-end" : "flex-start";

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          bottom: 100,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: justify,
          padding: "0 80px",
        }}
      >
        <SlideIn direction="left" distance={100} durationInFrames={14}>
          <div
            style={{
              background: bg,
              padding: "20px 36px",
              borderLeft: style === "gradient_modern" ? `6px solid ${accent}` : "none",
              maxWidth: 900,
            }}
          >
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontWeight: 900,
                fontSize: 42,
                color,
                lineHeight: 1.1,
                letterSpacing: -0.5,
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 500,
                  fontSize: 24,
                  color,
                  opacity: 0.85,
                  marginTop: 6,
                  letterSpacing: 1,
                  textTransform: "uppercase",
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
        </SlideIn>
      </div>
    </AbsoluteFill>
  );
};
