import React from "react";
import { AbsoluteFill, Img } from "remotion";

export type WatermarkCorner = "tl" | "tr" | "bl" | "br";

export interface WatermarkProps {
  src?: string;
  text?: string;
  corner?: WatermarkCorner;
  size?: number;
  opacity?: number;
  padding?: number;
  color?: string;
}

const POSITIONS: Record<WatermarkCorner, React.CSSProperties> = {
  tl: { top: 0, left: 0 },
  tr: { top: 0, right: 0 },
  bl: { bottom: 0, left: 0 },
  br: { bottom: 0, right: 0 },
};

export const Watermark: React.FC<WatermarkProps> = ({
  src,
  text,
  corner = "tr",
  size = 80,
  opacity = 0.75,
  padding = 48,
  color = "#FFFFFF",
}) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          ...POSITIONS[corner],
          margin: padding,
          opacity,
        }}
      >
        {src ? (
          <Img src={src} style={{ height: size, width: "auto" }} />
        ) : (
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 700,
              fontSize: size * 0.35,
              color,
              letterSpacing: 1,
              textTransform: "uppercase",
              textShadow: "0 2px 8px rgba(0,0,0,0.5)",
            }}
          >
            {text}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
