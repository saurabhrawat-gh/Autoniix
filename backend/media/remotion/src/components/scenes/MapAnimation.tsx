import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export interface MapPin {
  label: string;
  /** Normalized image coordinates (0..1 on both axes). */
  x: number;
  y: number;
  color?: string;
}

export interface MapAnimationProps {
  /** Background map image (equirectangular / political). */
  mapImageUrl?: string;
  pins: MapPin[];
  /** Optional travel route drawn sequentially through pins. */
  drawRoute?: boolean;
  bg?: string;
  accent?: string;
  pinRadius?: number;
  title?: string;
}

export const MapAnimation: React.FC<MapAnimationProps> = ({
  mapImageUrl,
  pins,
  drawRoute = true,
  bg = "#0A0A0A",
  accent = "#FFD60A",
  pinRadius = 16,
  title,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  const mapP = interpolate(frame, [0, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const perPin = Math.max(10, Math.floor((durationInFrames - 30) / Math.max(1, pins.length)));
  const toXY = (p: MapPin): [number, number] => [p.x * width, p.y * height];

  const routePathPoints: string[] = [];
  for (let i = 0; i < pins.length; i++) {
    const pinStart = 24 + i * perPin;
    const segP = interpolate(frame, [pinStart, pinStart + 12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    if (segP <= 0) break;
    if (i === 0) {
      const [x, y] = toXY(pins[0]!);
      routePathPoints.push(`M ${x} ${y}`);
    } else {
      const [px, py] = toXY(pins[i - 1]!);
      const [x, y] = toXY(pins[i]!);
      const nx = px + (x - px) * segP;
      const ny = py + (y - py) * segP;
      routePathPoints.push(`L ${nx} ${ny}`);
    }
  }
  const routePath = routePathPoints.join(" ");

  return (
    <AbsoluteFill style={{ backgroundColor: bg }}>
      {mapImageUrl && (
        <img
          src={mapImageUrl}
          alt=""
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: mapP * 0.9,
            filter: "grayscale(0.3) contrast(1.05) brightness(0.75)",
          }}
        />
      )}
      {title && (
        <div
          style={{
            position: "absolute",
            top: 60,
            left: 60,
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 56,
            color: "#fff",
            letterSpacing: -1,
            textShadow: "0 4px 24px rgba(0,0,0,0.8)",
          }}
        >
          {title}
        </div>
      )}

      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        {drawRoute && routePath && (
          <path
            d={routePath}
            stroke={accent}
            strokeWidth={4}
            strokeDasharray="10 6"
            fill="none"
            strokeLinecap="round"
          />
        )}
        {pins.map((p, i) => {
          const pinStart = 24 + i * perPin;
          const pinP = interpolate(frame, [pinStart, pinStart + 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          if (pinP <= 0) return null;
          const [x, y] = toXY(p);
          const col = p.color ?? accent;
          const r = pinRadius * pinP;
          return (
            <g key={i}>
              <circle cx={x} cy={y} r={r * 2.2} fill={col} opacity={0.2 * pinP} />
              <circle cx={x} cy={y} r={r} fill={col} />
              <text
                x={x + r + 10}
                y={y + 6}
                fill="#fff"
                fontFamily="Inter, sans-serif"
                fontWeight={700}
                fontSize={24}
                opacity={pinP}
                style={{ filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.8))" }}
              >
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
