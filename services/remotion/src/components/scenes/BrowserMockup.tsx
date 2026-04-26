import React from "react";
import { AbsoluteFill, Img, OffthreadVideo } from "remotion";

export interface BrowserMockupProps {
  url?: string;
  screenImageUrl?: string;
  screenVideoUrl?: string;
  title?: string;
  bg?: string;
  chromeBg?: string;
}

export const BrowserMockup: React.FC<BrowserMockupProps> = ({
  url = "example.com",
  screenImageUrl,
  screenVideoUrl,
  title,
  bg = "#0A0A0A",
  chromeBg = "#2B2B2E",
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          width: "78%",
          aspectRatio: "16/10",
          background: "#fff",
          borderRadius: 14,
          overflow: "hidden",
          boxShadow: "0 40px 120px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Chrome */}
        <div
          style={{
            background: chromeBg,
            padding: "12px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#FF605C" }} />
          <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#FFBD44" }} />
          <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#00CA4E" }} />
          <div
            style={{
              flex: 1,
              marginLeft: 20,
              padding: "6px 20px",
              background: "rgba(255,255,255,0.12)",
              borderRadius: 8,
              fontFamily: "Inter, sans-serif",
              color: "#eee",
              fontSize: 18,
            }}
          >
            🔒 {url}
          </div>
          {title && (
            <div
              style={{
                fontFamily: "Inter, sans-serif",
                color: "#bbb",
                fontSize: 18,
                paddingLeft: 16,
              }}
            >
              {title}
            </div>
          )}
        </div>

        {/* Viewport */}
        <div style={{ flex: 1, background: "#fff" }}>
          {screenVideoUrl ? (
            <OffthreadVideo
              src={screenVideoUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            />
          ) : screenImageUrl ? (
            <Img
              src={screenImageUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            />
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
