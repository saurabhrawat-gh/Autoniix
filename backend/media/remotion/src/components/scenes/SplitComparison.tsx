import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { SlideIn } from "../animations/SlideIn";

export interface SplitComparisonProps {
  leftLabel: string;
  rightLabel: string;
  leftContent?: string;
  rightContent?: string;
  leftImageUrl?: string;
  rightImageUrl?: string;
  leftColor?: string;
  rightColor?: string;
  vsBadge?: boolean;
  bg?: string;
}

export const SplitComparison: React.FC<SplitComparisonProps> = ({
  leftLabel,
  rightLabel,
  leftContent,
  rightContent,
  leftImageUrl,
  rightImageUrl,
  leftColor = "#FF3B30",
  rightColor = "#00E0FF",
  vsBadge = true,
  bg = "#0A0A0A",
}) => {
  const sideStyle = (color: string): React.CSSProperties => ({
    flex: 1,
    height: "100%",
    padding: 80,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    gap: 32,
    borderTop: `8px solid ${color}`,
    borderBottom: `8px solid ${color}`,
  });

  const label = (text: string, color: string): React.CSSProperties => ({
    fontFamily: "Inter, sans-serif",
    fontWeight: 900,
    fontSize: 96,
    color,
    letterSpacing: -2,
    textAlign: "center",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: bg, flexDirection: "row" }}>
      <SlideIn direction="left" distance={200} durationInFrames={18}>
        <div style={sideStyle(leftColor)}>
          {leftImageUrl && <Img src={leftImageUrl} style={{ maxWidth: "80%", maxHeight: 400 }} />}
          <div style={label(leftLabel, leftColor)}>{leftLabel}</div>
          {leftContent && (
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 36,
                color: "#fff",
                textAlign: "center",
                maxWidth: "90%",
                lineHeight: 1.3,
              }}
            >
              {leftContent}
            </div>
          )}
        </div>
      </SlideIn>

      <div style={{ width: 4, background: "rgba(255,255,255,0.15)" }} />

      <SlideIn direction="right" distance={200} durationInFrames={18}>
        <div style={sideStyle(rightColor)}>
          {rightImageUrl && <Img src={rightImageUrl} style={{ maxWidth: "80%", maxHeight: 400 }} />}
          <div style={label(rightLabel, rightColor)}>{rightLabel}</div>
          {rightContent && (
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 36,
                color: "#fff",
                textAlign: "center",
                maxWidth: "90%",
                lineHeight: 1.3,
              }}
            >
              {rightContent}
            </div>
          )}
        </div>
      </SlideIn>

      {vsBadge && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 180,
            height: 180,
            borderRadius: "50%",
            background: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 76,
            color: bg,
            boxShadow: "0 0 60px rgba(255,255,255,0.3)",
            letterSpacing: -2,
          }}
        >
          VS
        </div>
      )}
    </AbsoluteFill>
  );
};
