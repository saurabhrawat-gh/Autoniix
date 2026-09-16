import React from "react";
import { AbsoluteFill, Img, OffthreadVideo } from "remotion";

export type PhoneStyle = "iphone" | "android";

export interface PhoneMockupProps {
  screenImageUrl?: string;
  screenVideoUrl?: string;
  style?: PhoneStyle;
  tilt?: number;
  bg?: string;
  accentGlow?: string;
}

/**
 * A stylized phone frame with rounded corners, notch, and volume/power buttons.
 * Intentionally CSS-drawn (no external asset) so it's portable.
 */
export const PhoneMockup: React.FC<PhoneMockupProps> = ({
  screenImageUrl,
  screenVideoUrl,
  style = "iphone",
  tilt = 0,
  bg = "#0A0A0A",
  accentGlow = "#00E0FF",
}) => {
  const bezel = style === "iphone" ? 16 : 12;
  const radius = style === "iphone" ? 60 : 40;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          transform: `rotate(${tilt}deg)`,
          width: 480,
          height: 960,
          background: "#111",
          borderRadius: radius,
          padding: bezel,
          boxShadow: `0 40px 120px ${accentGlow}55, 0 0 0 2px rgba(255,255,255,0.1)`,
          position: "relative",
        }}
      >
        {/* Notch */}
        {style === "iphone" && (
          <div
            style={{
              position: "absolute",
              top: 8,
              left: "50%",
              transform: "translateX(-50%)",
              width: 160,
              height: 32,
              background: "#000",
              borderRadius: 999,
              zIndex: 2,
            }}
          />
        )}
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: radius - bezel,
            overflow: "hidden",
            background: "#000",
            position: "relative",
          }}
        >
          {screenVideoUrl ? (
            <OffthreadVideo
              src={screenVideoUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : screenImageUrl ? (
            <Img
              src={screenImageUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
