import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame } from "remotion";

export interface EndCardVideo {
  title: string;
  thumbnailUrl?: string;
}

export interface EndCardProps {
  title?: string;
  subtitle?: string;
  videos?: EndCardVideo[]; // up to 4 recommended video cards
  bg?: string;
  color?: string;
  accent?: string;
}

export const EndCard: React.FC<EndCardProps> = ({
  title = "WATCH NEXT",
  subtitle,
  videos = [],
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
}) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        opacity: fadeIn,
        padding: 80,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 48,
      }}
    >
      <div>
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 96,
            color,
            textAlign: "center",
            letterSpacing: -1,
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 500,
              fontSize: 32,
              color: accent,
              textAlign: "center",
              marginTop: 16,
              letterSpacing: 2,
              textTransform: "uppercase",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      {videos.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${videos.length}, 1fr)`, gap: 32, width: "90%" }}>
          {videos.slice(0, 4).map((v, i) => (
            <div
              key={i}
              style={{
                background: "#1a1a1a",
                border: `2px solid ${accent}`,
                overflow: "hidden",
              }}
            >
              {v.thumbnailUrl && (
                <Img src={v.thumbnailUrl} style={{ width: "100%", aspectRatio: "16/9", objectFit: "cover", display: "block" }} />
              )}
              <div
                style={{
                  padding: 16,
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 700,
                  fontSize: 22,
                  color,
                  lineHeight: 1.2,
                }}
              >
                {v.title}
              </div>
            </div>
          ))}
        </div>
      )}
    </AbsoluteFill>
  );
};
