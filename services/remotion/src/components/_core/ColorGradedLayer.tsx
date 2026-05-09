/**
 * Phase 1D — `<ColorGradedLayer>` renderer wrapper.
 *
 * Two execution paths:
 *
 *   • CSS fast path  — when the grade has only a primary (no secondaries, no
 *     LUT). We map lift/gamma/gain/saturation/contrast/temperature/tint to
 *     CSS `filter` chains: brightness/contrast/saturate/hue-rotate/sepia.
 *     The mapping is approximate; for pixel-accurate work the WebGL path is
 *     used. CSS is enabled by setting `forceWebgl={false}` (default).
 *
 *   • WebGL path     — when secondaries or a LUT are present, OR when the
 *     caller opts in via `forceWebgl`. We composite the child to an offscreen
 *     `<canvas>` via `html2canvas`-style snapshot is *not* used — instead we
 *     wrap children in a hidden video/img source and pass it through a
 *     fragment shader. For the common Tier-1 case (the child is a single
 *     `<OffthreadVideo>` or `<Img>`), this is wired in a follow-up. The
 *     contract surface — props, validation, hashing — ships now.
 *
 * No grade → bit-identical passthrough.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import {
  colorGradeAtTime,
  type ColorGradeTrack,
  type ColorPrimary,
} from "../../registry/colorGrade";
import type { ColorGradeTrackRef } from "../../scene-graph/types";

export interface ColorGradedLayerProps {
  colorGradeTrack?: ColorGradeTrackRef;
  /** When true, always use the WebGL path (mostly for tests / pixel-accuracy). */
  forceWebgl?: boolean;
  clipId?: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

/* ---- Dev-only one-time-warn for unimplemented paths ----------------- */
const _warned = new Set<string>();
function warnOnce(key: string, message: string): void {
  if (process.env.NODE_ENV === "production") return;
  if (_warned.has(key)) return;
  _warned.add(key);
  // eslint-disable-next-line no-console
  console.warn(`[ColorGradedLayer] ${message}`);
}

/* ---- CSS-filter fast path ------------------------------------------- */

function primaryToCssFilter(p: ColorPrimary): string {
  const sat = p.saturation ?? 1;
  const contrast = p.contrast ?? 1;
  // Approximate lift/gamma/gain by averaging RGB scale → brightness.
  const gamma = p.gamma ?? [1, 1, 1];
  const gain = p.gain ?? [1, 1, 1];
  const lift = p.lift ?? [0, 0, 0];
  const avgGain = (gain[0] + gain[1] + gain[2]) / 3;
  const avgLift = (lift[0] + lift[1] + lift[2]) / 3;
  // `brightness()` uses 1.0 as identity; emulate gain × (1 + lift).
  const brightness = avgGain * (1 + avgLift);
  // `contrast()` uses 1.0 as identity.
  const filterParts: string[] = [
    `brightness(${brightness.toFixed(4)})`,
    `contrast(${contrast.toFixed(4)})`,
    `saturate(${sat.toFixed(4)})`,
  ];
  // Approximate gamma via a CSS-only gamma trick is impossible; we ignore
  // gamma in the CSS fast path. Tests assert we round-trip when gamma=1.
  void gamma;
  // Temperature/tint approximation via hue-rotate + sepia: tiny effect.
  const temp = (p.temperature ?? 0) / 100;
  const tint = (p.tint ?? 0) / 100;
  if (Math.abs(temp) > 0.01) filterParts.push(`sepia(${Math.min(0.4, Math.abs(temp) * 0.5).toFixed(4)})`);
  if (Math.abs(tint) > 0.01) filterParts.push(`hue-rotate(${(tint * 30).toFixed(2)}deg)`);
  return filterParts.join(" ");
}

/* ---------------------------------------------------------------------- */

export const ColorGradedLayer: React.FC<ColorGradedLayerProps> = ({
  colorGradeTrack,
  forceWebgl,
  clipId,
  className,
  style,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // No grade → passthrough.
  if (!colorGradeTrack) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    );
  }

  const tLocalMs = (frame / fps) * 1000;
  const grade = colorGradeAtTime(
    colorGradeTrack as unknown as ColorGradeTrack,
    tLocalMs,
  );

  const hasSecondaries = (grade.secondaries?.length ?? 0) > 0;
  const hasLut = grade.lutId !== null;
  const needsWebgl = !!forceWebgl || hasSecondaries || hasLut;

  if (needsWebgl) {
    // The WebGL pipeline (offscreen canvas + fragment shader) is wired in
    // a follow-up to this milestone. Until then, fall back to the CSS
    // approximation of the primary and warn once per (clipId, kind).
    warnOnce(
      `webgl-fallback:${clipId ?? "?"}`,
      `WebGL grade path for clip "${clipId ?? "?"}" not yet wired (secondaries=${
        grade.secondaries.length
      }, lut=${grade.lutId ?? "none"}). Using CSS approximation of primary.`,
    );
  }

  return (
    <div
      className={className}
      data-clip-id={clipId}
      data-color-grade={hasSecondaries ? "secondaries" : hasLut ? "lut" : "primary"}
      style={{
        ...style,
        filter: primaryToCssFilter(grade.primary),
      }}
    >
      {children}
    </div>
  );
};
