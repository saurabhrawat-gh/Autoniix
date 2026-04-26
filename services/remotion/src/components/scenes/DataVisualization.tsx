import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { easings } from "../../utils/easing";
import { FadeIn } from "../animations/FadeIn";

export type ChartType = "bar" | "line" | "pie" | "donut" | "stacked_bar";

export interface ChartDatum {
  label: string;
  value: number;
  color?: string;
}

export interface DataVisualizationProps {
  type?: ChartType;
  title?: string;
  data: ChartDatum[];
  bg?: string;
  color?: string;
  accent?: string;
  unitSuffix?: string;
}

const PALETTE = ["#FFD60A", "#FF3B30", "#00E0FF", "#30D158", "#BF5AF2", "#FF9F0A"];

export const DataVisualization: React.FC<DataVisualizationProps> = ({
  type = "bar",
  title,
  data,
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
  unitSuffix = "",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();
  const animDur = Math.min(45, durationInFrames * 0.6);
  const p = easings.power2(
    interpolate(frame, [8, 8 + animDur], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  const colors = data.map((d, i) => d.color ?? PALETTE[i % PALETTE.length]);
  const max = Math.max(...data.map((d) => d.value));
  const total = data.reduce((a, d) => a + d.value, 0);

  return (
    <AbsoluteFill style={{ backgroundColor: bg, padding: 100 }}>
      {title && (
        <FadeIn durationInFrames={14}>
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 900,
              fontSize: 64,
              color,
              marginBottom: 48,
              letterSpacing: -1,
            }}
          >
            {title}
          </div>
        </FadeIn>
      )}

      <div style={{ flex: 1, display: "flex", gap: 40 }}>
        {(type === "bar" || type === "stacked_bar") && (
          <div style={{ flex: 1, display: "flex", alignItems: "flex-end", gap: 32 }}>
            {data.map((d, i) => {
              const h = (d.value / max) * 100 * p;
              return (
                <div
                  key={i}
                  style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    height: "100%",
                    justifyContent: "flex-end",
                    gap: 16,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "Inter, sans-serif",
                      fontWeight: 900,
                      fontSize: 36,
                      color: colors[i],
                    }}
                  >
                    {Math.round(d.value * p).toLocaleString()}
                    {unitSuffix}
                  </div>
                  <div
                    style={{
                      width: "100%",
                      height: `${h}%`,
                      background: colors[i],
                      borderRadius: 8,
                      boxShadow: `0 0 40px ${colors[i]}80`,
                    }}
                  />
                  <div
                    style={{
                      fontFamily: "Inter, sans-serif",
                      fontWeight: 600,
                      fontSize: 24,
                      color,
                      opacity: 0.8,
                      textAlign: "center",
                    }}
                  >
                    {d.label}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {type === "line" && (() => {
          const plotW = width - 200;
          const plotH = height - 320;
          const step = plotW / Math.max(1, data.length - 1);
          const toY = (v: number) => plotH - (v / max) * plotH * p;
          const points = data.map((d, i) => `${i * step},${toY(d.value)}`).join(" ");
          const visibleLen = p;
          return (
            <svg width={plotW} height={plotH} style={{ overflow: "visible" }}>
              <polyline
                fill="none"
                stroke={accent}
                strokeWidth={6}
                points={points}
                strokeDasharray={`${plotW * 2}`}
                strokeDashoffset={plotW * 2 * (1 - visibleLen)}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {data.map((d, i) => (
                <circle
                  key={i}
                  cx={i * step}
                  cy={toY(d.value)}
                  r={p > (i / data.length) ? 10 : 0}
                  fill={colors[i]}
                />
              ))}
            </svg>
          );
        })()}

        {(type === "pie" || type === "donut") && (() => {
          const size = Math.min(width - 200, height - 320);
          const r = size / 2;
          const cx = r;
          const cy = r;
          let angle = -Math.PI / 2;
          const arcs = data.map((d, i) => {
            const slice = (d.value / total) * 2 * Math.PI * p;
            const startX = cx + r * Math.cos(angle);
            const startY = cy + r * Math.sin(angle);
            angle += slice;
            const endX = cx + r * Math.cos(angle);
            const endY = cy + r * Math.sin(angle);
            const large = slice > Math.PI ? 1 : 0;
            const path = `M ${cx} ${cy} L ${startX} ${startY} A ${r} ${r} 0 ${large} 1 ${endX} ${endY} Z`;
            return <path key={i} d={path} fill={colors[i]} />;
          });
          return (
            <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
              <svg width={size} height={size}>
                {arcs}
                {type === "donut" && (
                  <circle cx={cx} cy={cy} r={r * 0.55} fill={bg} />
                )}
              </svg>
            </div>
          );
        })()}
      </div>
    </AbsoluteFill>
  );
};
