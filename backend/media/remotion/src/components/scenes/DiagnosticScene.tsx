import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export interface DiagnosticSceneProps {
  reason?: string;
  segmentId?: string;
  presetId?: string;
  videoId?: string;
}

/**
 * Highly visible diagnostic scene used as the *only* fallback path when a
 * preset is missing, a render is simplified, or test-mode synthesizes a
 * preview. Replaces the old `scene.placeholder.black` (which rendered fully
 * black and silently masked render failures).
 *
 * Render output is intentionally loud (red/yellow checkerboard, large text)
 * so any operator viewing the dashboard immediately knows the pipeline took a
 * fallback path — never confusable with a real, shippable render.
 */
export const DiagnosticScene: React.FC<DiagnosticSceneProps> = ({
  reason = "diagnostic",
  segmentId,
  presetId,
  videoId,
}) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const cellSize = Math.max(40, Math.floor(Math.min(width, height) / 16));
  const cols = Math.ceil(width / cellSize);
  const rows = Math.ceil(height / cellSize);
  const phase = Math.floor(frame / Math.max(1, Math.floor(fps / 4))) % 2;

  const cells: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const on = (r + c + phase) % 2 === 0;
      cells.push(
        <div
          key={`${r}-${c}`}
          style={{
            position: "absolute",
            left: c * cellSize,
            top: r * cellSize,
            width: cellSize,
            height: cellSize,
            backgroundColor: on ? "#7A0000" : "#3A0000",
          }}
        />,
      );
    }
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#3A0000" }}>
      {cells}
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          color: "#FFD60A",
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 900,
          textAlign: "center",
          padding: 40,
        }}
      >
        <div style={{ fontSize: Math.round(height * 0.06), letterSpacing: -1 }}>
          ⚠ DIAGNOSTIC FALLBACK
        </div>
        <div style={{ fontSize: Math.round(height * 0.035), marginTop: 16, color: "#FFFFFF" }}>
          {reason}
        </div>
        <div style={{ fontSize: Math.round(height * 0.022), marginTop: 24, color: "#FFAAAA" }}>
          {presetId ? `preset: ${presetId}` : null}
        </div>
        <div style={{ fontSize: Math.round(height * 0.022), color: "#FFAAAA" }}>
          {segmentId ? `segment: ${segmentId}` : null}
        </div>
        <div style={{ fontSize: Math.round(height * 0.022), color: "#FFAAAA" }}>
          {videoId ? `video: ${videoId}` : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
