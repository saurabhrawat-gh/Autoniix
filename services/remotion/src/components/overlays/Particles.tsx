import React from "react";
import { AbsoluteFill, random, useCurrentFrame, useVideoConfig } from "remotion";

export type ParticleStyle = "dust" | "snow" | "sparkles" | "confetti";

export interface ParticlesProps {
  style?: ParticleStyle;
  count?: number;
  color?: string;
  speed?: number; // pixels / second vertical drift
}

const STYLE_DEFAULTS: Record<
  ParticleStyle,
  { color: string; speed: number; sizeMin: number; sizeMax: number; count: number }
> = {
  dust: { color: "#FFFFFF", speed: 20, sizeMin: 1, sizeMax: 3, count: 80 },
  snow: { color: "#FFFFFF", speed: 80, sizeMin: 2, sizeMax: 6, count: 120 },
  sparkles: { color: "#FFD60A", speed: 15, sizeMin: 2, sizeMax: 5, count: 60 },
  confetti: { color: "#FF3B30", speed: 250, sizeMin: 4, sizeMax: 8, count: 120 },
};

export const Particles: React.FC<ParticlesProps> = ({
  style = "dust",
  count,
  color,
  speed,
}) => {
  const defaults = STYLE_DEFAULTS[style];
  const n = count ?? defaults.count;
  const c = color ?? defaults.color;
  const spd = speed ?? defaults.speed;

  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      {Array.from({ length: n }).map((_, i) => {
        const seed = `p${style}-${i}`;
        const x0 = random(`${seed}x`) * width;
        const phase = random(`${seed}p`) * 100;
        const size = defaults.sizeMin + random(`${seed}s`) * (defaults.sizeMax - defaults.sizeMin);
        const driftX = Math.sin(t * 0.5 + phase) * 20;
        const y = ((random(`${seed}y`) * height + t * spd) % (height + 40)) - 20;
        const opacity = style === "confetti" ? 1 : 0.4 + random(`${seed}o`) * 0.5;
        const rotate = style === "confetti" ? (t * 360 * random(`${seed}r`)) % 360 : 0;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x0 + driftX,
              top: y,
              width: size,
              height: style === "confetti" ? size * 2 : size,
              background: c,
              borderRadius: style === "confetti" ? 2 : "50%",
              opacity,
              transform: `rotate(${rotate}deg)`,
              boxShadow: style === "sparkles" ? `0 0 ${size * 3}px ${c}` : undefined,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
