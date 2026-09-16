import React from "react";
import { AbsoluteFill } from "remotion";
import { FadeIn } from "../animations/FadeIn";
import { SlideIn } from "../animations/SlideIn";

export type QuoteStyle = "serif_minimal" | "neon" | "bold_modern";

export interface QuoteCardProps {
  quote: string;
  source?: string;
  style?: QuoteStyle;
  bg?: string;
  accent?: string;
}

const STYLES: Record<QuoteStyle, { font: string; color: string; quoteMark: string }> = {
  serif_minimal: { font: "Georgia, serif", color: "#111", quoteMark: "“" },
  neon: { font: "Inter, sans-serif", color: "#0FF", quoteMark: "“" },
  bold_modern: { font: "Inter, sans-serif", color: "#FFF", quoteMark: "“" },
};

export const QuoteCard: React.FC<QuoteCardProps> = ({
  quote,
  source,
  style = "bold_modern",
  bg,
  accent = "#FF3B30",
}) => {
  const s = STYLES[style];
  const background = bg ?? (style === "serif_minimal" ? "#F5F1E8" : "#0A0A0A");

  return (
    <AbsoluteFill
      style={{
        backgroundColor: background,
        alignItems: "center",
        justifyContent: "center",
        padding: 120,
      }}
    >
      <FadeIn durationInFrames={20}>
        <SlideIn direction="up" distance={40} durationInFrames={20}>
          <div style={{ maxWidth: "75%", position: "relative" }}>
            <div
              style={{
                position: "absolute",
                top: -60,
                left: -40,
                fontSize: 240,
                color: accent,
                opacity: 0.35,
                fontFamily: s.font,
                lineHeight: 1,
              }}
            >
              {s.quoteMark}
            </div>
            <div
              style={{
                fontFamily: s.font,
                fontWeight: style === "serif_minimal" ? 400 : 700,
                fontSize: 68,
                lineHeight: 1.2,
                color: s.color,
                textAlign: "center",
                fontStyle: style === "serif_minimal" ? "italic" : "normal",
              }}
            >
              {quote}
            </div>
            {source && (
              <div
                style={{
                  marginTop: 48,
                  textAlign: "center",
                  fontFamily: "Inter, sans-serif",
                  fontSize: 28,
                  color: s.color,
                  opacity: 0.7,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                }}
              >
                — {source}
              </div>
            )}
          </div>
        </SlideIn>
      </FadeIn>
    </AbsoluteFill>
  );
};
