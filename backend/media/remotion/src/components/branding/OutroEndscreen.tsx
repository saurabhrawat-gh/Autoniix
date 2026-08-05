import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { FadeIn } from "../animations/FadeIn";
import { SlideIn } from "../animations/SlideIn";

export interface OutroEndscreenProps {
  channelName?: string;
  logoUrl?: string;
  cta?: string;
  subCta?: string;
  bg?: string;
  color?: string;
  accent?: string;
  socialLinks?: { label: string; handle: string }[];
}

export const OutroEndscreen: React.FC<OutroEndscreenProps> = ({
  channelName,
  logoUrl,
  cta = "LIKE & SUBSCRIBE",
  subCta = "New videos every week",
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FF0000",
  socialLinks = [],
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        padding: 120,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 48,
      }}
    >
      <FadeIn durationInFrames={20}>
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          {logoUrl && <Img src={logoUrl} style={{ height: 120 }} />}
          {channelName && (
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                fontWeight: 900,
                fontSize: 110,
                color,
                letterSpacing: -2,
              }}
            >
              {channelName}
            </div>
          )}
        </div>
      </FadeIn>

      <SlideIn direction="up" distance={60} durationInFrames={18} delay={8}>
        <div
          style={{
            background: accent,
            color: "#fff",
            padding: "28px 56px",
            borderRadius: 12,
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 56,
            letterSpacing: 3,
            textTransform: "uppercase",
            boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          }}
        >
          {cta}
        </div>
      </SlideIn>

      <FadeIn durationInFrames={20} delay={24}>
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 500,
            fontSize: 32,
            color,
            opacity: 0.8,
            letterSpacing: 1,
          }}
        >
          {subCta}
        </div>
      </FadeIn>

      {socialLinks.length > 0 && (
        <FadeIn durationInFrames={20} delay={36}>
          <div style={{ display: "flex", gap: 48 }}>
            {socialLinks.map((s, i) => (
              <div
                key={i}
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontSize: 26,
                  color,
                  letterSpacing: 1,
                }}
              >
                <span style={{ color: accent, fontWeight: 900, marginRight: 12 }}>{s.label}</span>
                {s.handle}
              </div>
            ))}
          </div>
        </FadeIn>
      )}
    </AbsoluteFill>
  );
};
