import React from "react";
import { AbsoluteFill } from "remotion";
import { SlideIn } from "../animations/SlideIn";

export interface ChapterMarkerProps {
  chapter?: string;
  title: string;
  accent?: string;
  color?: string;
  position?: "top" | "bottom";
}

export const ChapterMarker: React.FC<ChapterMarkerProps> = ({
  chapter,
  title,
  accent = "#FFD60A",
  color = "#FFFFFF",
  position = "top",
}) => {
  const posStyle: React.CSSProperties =
    position === "top" ? { top: 60, left: 60 } : { bottom: 60, left: 60 };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", ...posStyle }}>
        <SlideIn direction="left" distance={80} durationInFrames={14}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            {chapter && (
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 900,
                  fontSize: 28,
                  color: accent,
                  letterSpacing: 2,
                }}
              >
                {chapter}
              </div>
            )}
            <div style={{ width: 2, height: 36, background: color, opacity: 0.6 }} />
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontWeight: 700,
                fontSize: 36,
                color,
                letterSpacing: -0.5,
              }}
            >
              {title}
            </div>
          </div>
        </SlideIn>
      </div>
    </AbsoluteFill>
  );
};
