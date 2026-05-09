import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import {
  computeScrambleDecode,
  type ScrambleRevealMode,
} from "../../registry/textAnimations";

/**
 * Phase 1B — Scramble-decode text reveal. Letters cycle through a charset
 * before settling, swept left-to-right (or other modes) over `durationMs`.
 *
 * Pure compute happens in `computeScrambleDecode`; this is the React shell.
 */
export interface ScrambleDecodeProps {
  text: string;
  /** Reveal duration in frames (preferred) or milliseconds (alternative). */
  durationInFrames?: number;
  durationMs?: number;
  charset?: string;
  revealMode?: ScrambleRevealMode;
  /** Glyph swap rate per second per char. Default 24. */
  scrambleFps?: number;
  /** Deterministic seed string. Default derived from text+duration. */
  seed?: string | number;
  delayInFrames?: number;
  style?: React.CSSProperties;
}

export const ScrambleDecode: React.FC<ScrambleDecodeProps> = ({
  text,
  durationInFrames,
  durationMs,
  charset,
  revealMode = "left_to_right",
  scrambleFps,
  seed,
  delayInFrames = 0,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - delayInFrames);
  const tLocalMs = (localFrame / fps) * 1000;
  const resolvedDurationMs =
    durationMs ?? ((durationInFrames ?? 30) / fps) * 1000;

  const { visible } = computeScrambleDecode(
    {
      text,
      durationMs: resolvedDurationMs,
      charset,
      revealMode,
      scrambleFps,
      seed,
    },
    tLocalMs,
  );

  // Use a fixed-width-ish span to prevent layout shift while glyphs change.
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>{visible}</span>
  );
};
