import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { msToFrames } from "../../utils/timing";

/**
 * Word-level caption overlay driven by forced-alignment data. Expects an array
 * of `{word, startMs, endMs}` cues. Highlights the currently-spoken word and
 * groups neighbouring words into readable chunks on screen.
 *
 * This is the Phase 3 upgrade over `CaptionOverlay` which only worked at the
 * phrase level. Alignment data typically comes from Whisper with
 * `word_timestamps=True` or forced aligners like MFA / gentle / aeneas.
 */

export interface WordCue {
  word: string;
  startMs: number;
  endMs: number;
}

export type WordCaptionStyle =
  | "karaoke_highlight"
  | "pop_active"
  | "underline_active";

export interface WordAlignedCaptionProps {
  words: WordCue[];
  /** Max words in a single visible chunk at once. */
  chunkSize?: number;
  style?: WordCaptionStyle;
  activeColor?: string;
  idleColor?: string;
  bg?: string;
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: number;
  position?: "top" | "center" | "bottom";
  /**
   * Words hang around for `tailMs` after their endMs finishes so the chunk
   * doesn't vanish the moment the last syllable ends.
   */
  tailMs?: number;
}

export const WordAlignedCaption: React.FC<WordAlignedCaptionProps> = ({
  words,
  chunkSize = 6,
  style = "karaoke_highlight",
  activeColor = "#FFD60A",
  idleColor = "#FFFFFF",
  bg = "rgba(0,0,0,0.55)",
  fontFamily = "Inter, sans-serif",
  fontSize = 56,
  fontWeight = 900,
  position = "bottom",
  tailMs = 150,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  // Find the active word
  const activeIdx = words.findIndex(
    (w) => currentMs >= w.startMs && currentMs < w.endMs + tailMs,
  );
  if (activeIdx === -1) {
    // Look ahead: find the next word within 250ms so the chunk preloads
    const upcoming = words.findIndex((w) => w.startMs > currentMs && w.startMs - currentMs < 250);
    if (upcoming === -1) return null;
    return renderChunk(upcoming, -1);
  }

  return renderChunk(activeIdx, activeIdx);

  function renderChunk(anchor: number, activeWithinChunk: number) {
    const half = Math.floor(chunkSize / 2);
    const start = Math.max(0, anchor - half);
    const end = Math.min(words.length, start + chunkSize);
    const chunk = words.slice(start, end);
    const activeRel = activeWithinChunk - start;

    const posStyle: React.CSSProperties =
      position === "top"
        ? { top: "12%", left: 0, right: 0, justifyContent: "center", alignItems: "flex-start" }
        : position === "center"
          ? { inset: 0, justifyContent: "center", alignItems: "center" }
          : { bottom: "12%", left: 0, right: 0, justifyContent: "center", alignItems: "flex-end" };

    return (
      <AbsoluteFill style={{ pointerEvents: "none", display: "flex", ...posStyle }}>
        <div
          style={{
            background: bg,
            padding: "18px 36px",
            borderRadius: 12,
            maxWidth: "88%",
            display: "flex",
            flexWrap: "wrap",
            gap: 14,
            justifyContent: "center",
            fontFamily,
            fontSize,
            fontWeight,
            lineHeight: 1.2,
          }}
        >
          {chunk.map((w, i) => {
            const isActive = i === activeRel;
            const styleInner = wordStyle(style, isActive, activeColor, idleColor);
            return (
              <span key={`${start + i}-${w.word}`} style={styleInner}>
                {w.word}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }
};

function wordStyle(
  style: WordCaptionStyle,
  isActive: boolean,
  activeColor: string,
  idleColor: string,
): React.CSSProperties {
  if (style === "karaoke_highlight") {
    return {
      color: isActive ? activeColor : idleColor,
      textShadow: isActive ? `0 0 16px ${activeColor}` : "none",
    };
  }
  if (style === "pop_active") {
    return {
      color: isActive ? activeColor : idleColor,
      display: "inline-block",
      transform: isActive ? "scale(1.15)" : "scale(1)",
      transformOrigin: "bottom center",
    };
  }
  // underline_active
  return {
    color: idleColor,
    borderBottom: isActive ? `4px solid ${activeColor}` : "4px solid transparent",
    paddingBottom: 2,
  };
}

/** Tiny helper so outside callers can convert to frame-based cues when needed. */
export function wordCueToFrame(cue: WordCue, fps: number) {
  return {
    startFrame: msToFrames(cue.startMs, fps),
    endFrame: msToFrames(cue.endMs, fps),
  };
}
