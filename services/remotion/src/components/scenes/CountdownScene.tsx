import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

export type CountdownStyle = "numeric" | "dial" | "ticking";

export interface CountdownSceneProps {
  startSeconds: number;
  endSeconds?: number;
  style?: CountdownStyle;
  bg?: string;
  color?: string;
  accent?: string;
  suffix?: string;
}

export const CountdownScene: React.FC<CountdownSceneProps> = ({
  startSeconds,
  endSeconds = 0,
  style = "numeric",
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FF3B30",
  suffix,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const totalS = durationInFrames / fps;
  const progress = Math.min(1, t / totalS);
  const current = Math.max(endSeconds, Math.round(startSeconds + (endSeconds - startSeconds) * progress));

  // Spring bounce on each integer change
  const intFrame = Math.floor((current / Math.max(1, startSeconds)) * durationInFrames);
  const pop = spring({
    frame: frame - intFrame,
    fps,
    config: { damping: 10, stiffness: 220 },
    from: 1.15,
    to: 1,
  });

  if (style === "dial") {
    const size = 600;
    const r = size / 2 - 20;
    const circum = 2 * Math.PI * r;
    const fraction = 1 - progress;
    return (
      <AbsoluteFill style={{ backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
        <svg width={size} height={size}>
          <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.12)" strokeWidth={14} fill="none" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={accent}
            strokeWidth={14}
            fill="none"
            strokeDasharray={circum}
            strokeDashoffset={circum * (1 - fraction)}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            strokeLinecap="round"
          />
          <text
            x={size / 2}
            y={size / 2}
            dominantBaseline="central"
            textAnchor="middle"
            fill={color}
            fontFamily="Inter, sans-serif"
            fontWeight={900}
            fontSize={180}
          >
            {current}
          </text>
        </svg>
        {suffix && (
          <div style={{ marginTop: 32, fontSize: 42, color, fontFamily: "Inter, sans-serif", opacity: 0.8 }}>
            {suffix}
          </div>
        )}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontFamily: "Inter, sans-serif",
          fontWeight: 900,
          fontSize: 420,
          color: accent,
          lineHeight: 1,
          transform: `scale(${pop})`,
          textShadow: `0 0 80px ${accent}80`,
        }}
      >
        {current}
      </div>
      {suffix && (
        <div
          style={{
            marginTop: 24,
            fontFamily: "Inter, sans-serif",
            fontWeight: 700,
            fontSize: 48,
            color,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          {suffix}
        </div>
      )}
    </AbsoluteFill>
  );
};
