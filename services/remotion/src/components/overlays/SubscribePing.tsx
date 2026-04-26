import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

/**
 * A short "Subscribe!" chip that pops in, dwells, then slides out. Intended to
 * be mounted in a Sequence timed to the desired moment (not full duration).
 */
export type SubscribeStyle = "red_button" | "minimal_pill" | "neon";

export interface SubscribePingProps {
  text?: string;
  style?: SubscribeStyle;
  position?: "bl" | "br" | "tl" | "tr";
  dwellFrames?: number;
}

export const SubscribePing: React.FC<SubscribePingProps> = ({
  text = "SUBSCRIBE",
  style = "red_button",
  position = "br",
  dwellFrames = 60,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enter = spring({ frame, fps, from: 0, to: 1, config: { damping: 12, stiffness: 140 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const pulse = 1 + 0.06 * Math.sin((frame / fps) * 2 * Math.PI * 1.5);
  const p = Math.min(enter, exit);
  // dwellFrames is implicit — the Sequence durationInFrames is the dwell.
  void dwellFrames;

  const bg =
    style === "red_button" ? "#FF0000" : style === "neon" ? "#0A0A0A" : "rgba(255,255,255,0.95)";
  const color = style === "minimal_pill" ? "#0A0A0A" : "#FFFFFF";
  const border = style === "neon" ? "2px solid #00E0FF" : "none";
  const boxShadow =
    style === "neon"
      ? "0 0 20px #00E0FF, 0 0 40px #00E0FF"
      : "0 8px 30px rgba(0,0,0,0.4)";

  const pos: React.CSSProperties = {};
  if (position.includes("t")) pos.top = 60;
  else pos.bottom = 60;
  if (position.includes("l")) pos.left = 60;
  else pos.right = 60;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          ...pos,
          transform: `scale(${p * pulse})`,
          opacity: p,
          transformOrigin: "bottom right",
          padding: "18px 32px",
          background: bg,
          color,
          border,
          borderRadius: style === "minimal_pill" ? 999 : 12,
          fontFamily: "Inter, sans-serif",
          fontWeight: 900,
          fontSize: 36,
          letterSpacing: 2,
          textTransform: "uppercase",
          boxShadow,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
