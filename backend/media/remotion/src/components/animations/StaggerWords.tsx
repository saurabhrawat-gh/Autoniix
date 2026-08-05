import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import {
  computeStaggerWords,
  type EasingName,
} from "../../registry/textAnimations";

/**
 * Phase 1B — Per-word staggered reveal.
 *
 * Each word enters with a configurable child animation. The child is driven
 * by per-word `progress` (0..1) so the inner animation is fully deterministic.
 *
 * Built-in child animations:
 *   • fade        (opacity 0→1)
 *   • slide_up    (translateY 16px → 0; opacity 0→1)
 *   • scale_pop   (scale 0.6→1.0 with overshoot; opacity 0→1)
 */
export type StaggerChildAnim = "fade" | "slide_up" | "scale_pop";

export interface StaggerWordsProps {
  words: string[];
  /** Delay between word entrances (frames). Default 4. */
  delayPerWordInFrames?: number;
  /** Per-word entrance duration (frames). Default 12. */
  wordDurationInFrames?: number;
  childAnim?: StaggerChildAnim;
  easing?: EasingName;
  delayInFrames?: number;
  /** Space between words (px). Default 12. */
  gapPx?: number;
  style?: React.CSSProperties;
  wordStyle?: React.CSSProperties;
}

function applyChildAnim(
  anim: StaggerChildAnim,
  progress: number,
): React.CSSProperties {
  switch (anim) {
    case "fade":
      return { opacity: progress };
    case "slide_up":
      return {
        opacity: progress,
        transform: `translateY(${(1 - progress) * 16}px)`,
      };
    case "scale_pop": {
      const overshoot = progress < 0.7
        ? 0.6 + (progress / 0.7) * 0.5
        : 1.10 - ((progress - 0.7) / 0.3) * 0.10;
      return {
        opacity: progress,
        transform: `scale(${overshoot})`,
        transformOrigin: "center bottom",
      };
    }
  }
}

export const StaggerWords: React.FC<StaggerWordsProps> = ({
  words,
  delayPerWordInFrames = 4,
  wordDurationInFrames = 12,
  childAnim = "slide_up",
  easing = "ease_out_cubic",
  delayInFrames = 0,
  gapPx = 12,
  style,
  wordStyle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - delayInFrames);
  const tLocalMs = (localFrame / fps) * 1000;

  const { perWord } = computeStaggerWords(
    {
      words,
      delayPerWordMs: (delayPerWordInFrames / fps) * 1000,
      wordDurationMs: (wordDurationInFrames / fps) * 1000,
      easing,
    },
    tLocalMs,
  );

  return (
    <span
      style={{
        display: "inline-flex",
        flexWrap: "wrap",
        gap: gapPx,
        ...style,
      }}
    >
      {perWord.map((w, i) => (
        <span
          key={i}
          style={{
            display: "inline-block",
            ...wordStyle,
            ...applyChildAnim(childAnim, w.progress),
          }}
        >
          {w.word}
        </span>
      ))}
    </span>
  );
};
