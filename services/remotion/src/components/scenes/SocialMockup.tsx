import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { SlideIn } from "../animations/SlideIn";

export type SocialPlatform = "twitter" | "instagram" | "youtube_comment" | "tiktok_caption";

export interface SocialMockupProps {
  platform?: SocialPlatform;
  author: string;
  handle?: string;
  avatarUrl?: string;
  text: string;
  likes?: number;
  imageUrl?: string;
  verified?: boolean;
  bg?: string;
}

export const SocialMockup: React.FC<SocialMockupProps> = ({
  platform = "twitter",
  author,
  handle,
  avatarUrl,
  text,
  likes,
  imageUrl,
  verified,
  bg = "#0A0A0A",
}) => {
  const cardBg = platform === "instagram" ? "#FFFFFF" : platform === "tiktok_caption" ? "rgba(0,0,0,0.85)" : "#15202B";
  const fg = platform === "instagram" ? "#0A0A0A" : "#FFFFFF";
  const muted = platform === "instagram" ? "#666" : "rgba(255,255,255,0.65)";

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        padding: 120,
      }}
    >
      <SlideIn direction="up" distance={60} durationInFrames={18}>
        <div
          style={{
            width: 820,
            background: cardBg,
            color: fg,
            borderRadius: 16,
            padding: 32,
            fontFamily: "Inter, system-ui, sans-serif",
            boxShadow: "0 30px 80px rgba(0,0,0,0.5)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
            {avatarUrl ? (
              <Img src={avatarUrl} style={{ width: 64, height: 64, borderRadius: "50%" }} />
            ) : (
              <div style={{ width: 64, height: 64, borderRadius: "50%", background: "#888" }} />
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 900, fontSize: 26, display: "flex", alignItems: "center", gap: 8 }}>
                {author}
                {verified && (
                  <span style={{ color: "#1D9BF0", fontSize: 24 }}>✓</span>
                )}
              </div>
              {handle && (
                <div style={{ color: muted, fontSize: 20 }}>{handle}</div>
              )}
            </div>
            {platform === "twitter" && (
              <div style={{ color: "#1D9BF0", fontSize: 40, fontWeight: 900 }}>𝕏</div>
            )}
          </div>

          <div style={{ fontSize: 32, lineHeight: 1.4, whiteSpace: "pre-wrap" }}>{text}</div>

          {imageUrl && (
            <div style={{ marginTop: 16, borderRadius: 12, overflow: "hidden" }}>
              <Img src={imageUrl} style={{ width: "100%", display: "block" }} />
            </div>
          )}

          {likes !== undefined && (
            <div
              style={{
                marginTop: 20,
                color: muted,
                fontSize: 22,
                display: "flex",
                gap: 24,
              }}
            >
              <span>♥ {likes.toLocaleString()}</span>
            </div>
          )}
        </div>
      </SlideIn>
    </AbsoluteFill>
  );
};
