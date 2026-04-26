import React from "react";
import { AbsoluteFill } from "remotion";
import { SlideIn } from "../animations/SlideIn";

export type BulletStyle = "check" | "number" | "dot" | "arrow";

export interface ListAnimationProps {
  items: string[];
  title?: string;
  bullet?: BulletStyle;
  bg?: string;
  color?: string;
  accent?: string;
  font?: string;
  staggerFrames?: number;
}

const BULLETS: Record<BulletStyle, (i: number, accent: string) => React.ReactNode> = {
  check: (_i, a) => <span style={{ color: a, marginRight: 24 }}>✓</span>,
  number: (i, a) => (
    <span style={{ color: a, marginRight: 24, fontWeight: 900 }}>{i + 1}.</span>
  ),
  dot: (_i, a) => <span style={{ color: a, marginRight: 24 }}>•</span>,
  arrow: (_i, a) => <span style={{ color: a, marginRight: 24 }}>→</span>,
};

export const ListAnimation: React.FC<ListAnimationProps> = ({
  items,
  title,
  bullet = "check",
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
  font = "Inter, sans-serif",
  staggerFrames = 10,
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        padding: 100,
        justifyContent: "center",
      }}
    >
      {title && (
        <SlideIn direction="up" distance={30} durationInFrames={14}>
          <div
            style={{
              fontFamily: font,
              fontWeight: 900,
              fontSize: 72,
              color,
              marginBottom: 48,
              letterSpacing: -1,
            }}
          >
            {title}
          </div>
        </SlideIn>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {items.map((item, i) => (
          <SlideIn
            key={i}
            direction="left"
            distance={60}
            delay={(i + 1) * staggerFrames}
            durationInFrames={14}
          >
            <div
              style={{
                fontFamily: font,
                fontWeight: 600,
                fontSize: 54,
                color,
                display: "flex",
                alignItems: "center",
                lineHeight: 1.2,
              }}
            >
              {BULLETS[bullet](i, accent)}
              <span>{item}</span>
            </div>
          </SlideIn>
        ))}
      </div>
    </AbsoluteFill>
  );
};
