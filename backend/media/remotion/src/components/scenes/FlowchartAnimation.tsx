import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export interface FlowNode {
  id: string;
  label: string;
  x: number;
  y: number;
  color?: string;
  shape?: "box" | "round" | "diamond";
}

export interface FlowEdge {
  from: string;
  to: string;
  label?: string;
}

export interface FlowchartAnimationProps {
  nodes: FlowNode[];
  edges: FlowEdge[];
  title?: string;
  bg?: string;
  color?: string;
  accent?: string;
  nodeWidth?: number;
  nodeHeight?: number;
}

const PALETTE = ["#FFD60A", "#FF3B30", "#00E0FF", "#30D158", "#BF5AF2", "#FF9F0A"];

export const FlowchartAnimation: React.FC<FlowchartAnimationProps> = ({
  nodes,
  edges,
  title,
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
  nodeWidth = 260,
  nodeHeight = 90,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();
  const totalSteps = nodes.length + edges.length;
  const perStep = Math.max(8, Math.floor((durationInFrames - 20) / Math.max(1, totalSteps)));

  const byId = new Map(nodes.map((n) => [n.id, n]));

  return (
    <AbsoluteFill style={{ backgroundColor: bg, padding: 80 }}>
      {title && (
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 56,
            color,
            marginBottom: 32,
            letterSpacing: -1,
          }}
        >
          {title}
        </div>
      )}
      <svg
        width={width - 160}
        height={height - 200}
        style={{ overflow: "visible", position: "relative" }}
      >
        {/* Edges first (below nodes) */}
        {edges.map((e, i) => {
          const from = byId.get(e.from);
          const to = byId.get(e.to);
          if (!from || !to) return null;
          const start = 10 + (nodes.length + i) * perStep;
          const p = interpolate(frame, [start, start + 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          if (p <= 0) return null;
          const x1 = from.x * (width - 160);
          const y1 = from.y * (height - 200);
          const x2 = to.x * (width - 160);
          const y2 = to.y * (height - 200);
          const dx = (x2 - x1) * p;
          const dy = (y2 - y1) * p;
          const endX = x1 + dx;
          const endY = y1 + dy;
          return (
            <g key={`e-${i}`}>
              <line
                x1={x1}
                y1={y1}
                x2={endX}
                y2={endY}
                stroke={accent}
                strokeWidth={3}
                strokeDasharray="8 4"
                markerEnd={p >= 0.95 ? "url(#arrow)" : undefined}
              />
              {e.label && p > 0.5 && (
                <text
                  x={(x1 + endX) / 2}
                  y={(y1 + endY) / 2 - 10}
                  fill={color}
                  fontFamily="Inter, sans-serif"
                  fontSize={18}
                  textAnchor="middle"
                  opacity={(p - 0.5) * 2}
                >
                  {e.label}
                </text>
              )}
            </g>
          );
        })}

        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill={accent} />
          </marker>
        </defs>

        {/* Nodes on top */}
        {nodes.map((n, i) => {
          const start = 10 + i * perStep;
          const p = interpolate(frame, [start, start + 12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          if (p <= 0) return null;
          const x = n.x * (width - 160);
          const y = n.y * (height - 200);
          const col = n.color ?? PALETTE[i % PALETTE.length];
          const w = nodeWidth * p;
          const h = nodeHeight * p;

          return (
            <g key={n.id} transform={`translate(${x - w / 2}, ${y - h / 2})`}>
              {n.shape === "diamond" ? (
                <polygon
                  points={`${w / 2},0 ${w},${h / 2} ${w / 2},${h} 0,${h / 2}`}
                  fill={col}
                  opacity={p}
                />
              ) : (
                <rect
                  width={w}
                  height={h}
                  rx={n.shape === "round" ? h / 2 : 12}
                  fill={col}
                  opacity={p}
                />
              )}
              <text
                x={w / 2}
                y={h / 2 + 8}
                fill="#0A0A0A"
                fontFamily="Inter, sans-serif"
                fontWeight={700}
                fontSize={22}
                textAnchor="middle"
                opacity={p}
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
