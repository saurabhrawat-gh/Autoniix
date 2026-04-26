import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export type ProgressPosition = "top" | "bottom";
export type ProgressStyle = "thin_line" | "segmented" | "rounded_fat";

export interface ProgressBarProps {
  position?: ProgressPosition;
  style?: ProgressStyle;
  color?: string;
  bg?: string;
  heightPx?: number;
  segments?: number; // only used when style = "segmented"
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  position = "top",
  style = "thin_line",
  color = "#FFD60A",
  bg = "rgba(255,255,255,0.15)",
  heightPx = 6,
  segments = 10,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = Math.min(1, frame / Math.max(1, durationInFrames));

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    [position]: 0,
    height: style === "rounded_fat" ? heightPx * 2 : heightPx,
    background: bg,
    padding: style === "segmented" ? 4 : 0,
    display: "flex",
    gap: style === "segmented" ? 4 : 0,
  };

  if (style === "segmented") {
    const filled = Math.floor(p * segments);
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <div style={containerStyle}>
          {Array.from({ length: segments }).map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                background: i < filled ? color : "transparent",
                borderRadius: 2,
              }}
            />
          ))}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={containerStyle}>
        <div
          style={{
            width: `${p * 100}%`,
            height: "100%",
            background: color,
            borderRadius: style === "rounded_fat" ? heightPx : 0,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
