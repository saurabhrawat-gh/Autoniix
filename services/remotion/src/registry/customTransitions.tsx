import React from "react";
import { AbsoluteFill } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

/**
 * Phase 2 custom transition presenters that @remotion/transitions doesn't ship.
 * Each returns a `TransitionPresentation<{}>` which TransitionSeries can render.
 */

// BlurSwap: outgoing blurs out & fades, incoming blurs in & fades up

const BlurSwapPresenter: React.FC<
  TransitionPresentationComponentProps<{ maxBlurPx: number }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { maxBlurPx } = passedProps;
  const p = presentationProgress;
  const style: React.CSSProperties =
    presentationDirection === "entering"
      ? {
          filter: `blur(${(1 - p) * maxBlurPx}px)`,
          opacity: p,
        }
      : {
          filter: `blur(${p * maxBlurPx}px)`,
          opacity: 1 - p,
        };
  return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
};

export const blurSwap = (
  opts: { maxBlurPx?: number } = {},
): TransitionPresentation<{ maxBlurPx: number }> => ({
  component: BlurSwapPresenter,
  props: { maxBlurPx: opts.maxBlurPx ?? 30 },
});

// Iris: circular mask expands/contracts around center

const IrisPresenter: React.FC<
  TransitionPresentationComponentProps<{ direction: "open" | "close" }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { direction } = passedProps;
  const p = presentationProgress;
  // For `open`: incoming reveals as circle grows; outgoing shrinks.
  // For `close`: opposite.
  const radiusPct =
    presentationDirection === "entering"
      ? direction === "open"
        ? p * 150
        : (1 - p) * 150
      : direction === "open"
        ? (1 - p) * 150
        : p * 150;

  const mask = `radial-gradient(circle at 50% 50%, #000 ${radiusPct}%, transparent ${radiusPct + 2}%)`;

  return (
    <AbsoluteFill
      style={{
        maskImage: mask,
        WebkitMaskImage: mask,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const iris = (
  opts: { direction?: "open" | "close" } = {},
): TransitionPresentation<{ direction: "open" | "close" }> => ({
  component: IrisPresenter,
  props: { direction: opts.direction ?? "open" },
});

// WhipPan: fast horizontal motion blur sweep between scenes

const WhipPanPresenter: React.FC<
  TransitionPresentationComponentProps<{ dir: "left" | "right"; maxBlurPx: number }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { dir, maxBlurPx } = passedProps;
  const p = presentationProgress;
  const sign = dir === "left" ? -1 : 1;

  // bell curve: blur peaks mid-transition
  const blurAmt = Math.sin(p * Math.PI) * maxBlurPx;
  const translate =
    presentationDirection === "entering"
      ? -sign * (1 - p) * 100 // slide in from opposite edge
      : sign * p * 100; // slide out toward dir

  return (
    <AbsoluteFill
      style={{
        transform: `translateX(${translate}%)`,
        filter: `blur(${blurAmt}px)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const whipPan = (
  opts: { dir?: "left" | "right"; maxBlurPx?: number } = {},
): TransitionPresentation<{ dir: "left" | "right"; maxBlurPx: number }> => ({
  component: WhipPanPresenter,
  props: { dir: opts.dir ?? "left", maxBlurPx: opts.maxBlurPx ?? 24 },
});

// Cover: incoming slides over stationary outgoing (outgoing holds, incoming overtakes)

const CoverPresenter: React.FC<
  TransitionPresentationComponentProps<{ dir: "left" | "right" | "up" | "down" }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { dir } = passedProps;
  const p = presentationProgress;

  if (presentationDirection === "exiting") {
    // Outgoing scene stays in place
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }

  // Incoming slides in from `dir` edge
  const axis = dir === "left" || dir === "right" ? "X" : "Y";
  const sign = dir === "left" || dir === "up" ? -1 : 1;
  const offset = -sign * (1 - p) * 100;
  return (
    <AbsoluteFill style={{ transform: `translate${axis}(${offset}%)` }}>
      {children}
    </AbsoluteFill>
  );
};

export const cover = (
  opts: { dir?: "left" | "right" | "up" | "down" } = {},
): TransitionPresentation<{ dir: "left" | "right" | "up" | "down" }> => ({
  component: CoverPresenter,
  props: { dir: opts.dir ?? "right" },
});

// ZoomPunch: outgoing scales up + blurs out; incoming scales in from zoom

const ZoomPunchPresenter: React.FC<
  TransitionPresentationComponentProps<{ maxZoom: number; maxBlurPx: number }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { maxZoom, maxBlurPx } = passedProps;
  const p = presentationProgress;
  const style: React.CSSProperties =
    presentationDirection === "entering"
      ? {
          transform: `scale(${1 + (1 - p) * (maxZoom - 1)})`,
          filter: `blur(${(1 - p) * maxBlurPx}px)`,
          opacity: p,
        }
      : {
          transform: `scale(${1 + p * (maxZoom - 1)})`,
          filter: `blur(${p * maxBlurPx}px)`,
          opacity: 1 - p,
        };
  return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
};

export const zoomPunch = (
  opts: { maxZoom?: number; maxBlurPx?: number } = {},
): TransitionPresentation<{ maxZoom: number; maxBlurPx: number }> => ({
  component: ZoomPunchPresenter,
  props: { maxZoom: opts.maxZoom ?? 2.4, maxBlurPx: opts.maxBlurPx ?? 16 },
});

// GlitchCut: very fast RGB-split flicker while swapping

const GlitchCutPresenter: React.FC<
  TransitionPresentationComponentProps<{ splitPx: number }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { splitPx } = passedProps;
  const p = presentationProgress;
  // Glitch intensity peaks mid-cut
  const g = Math.sin(p * Math.PI);
  const offset = g * splitPx;

  if (presentationDirection === "entering") {
    return (
      <AbsoluteFill style={{ opacity: p }}>
        <div style={{ position: "absolute", inset: 0, filter: `drop-shadow(${offset}px 0 0 #f06), drop-shadow(${-offset}px 0 0 #0ef)`, mixBlendMode: "screen" }}>
          {children}
        </div>
        <div style={{ position: "absolute", inset: 0 }}>{children}</div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ opacity: 1 - p }}>
      <div style={{ position: "absolute", inset: 0, filter: `drop-shadow(${-offset}px 0 0 #f06), drop-shadow(${offset}px 0 0 #0ef)`, mixBlendMode: "screen" }}>
        {children}
      </div>
      <div style={{ position: "absolute", inset: 0 }}>{children}</div>
    </AbsoluteFill>
  );
};

export const glitchCut = (
  opts: { splitPx?: number } = {},
): TransitionPresentation<{ splitPx: number }> => ({
  component: GlitchCutPresenter,
  props: { splitPx: opts.splitPx ?? 18 },
});

// Shatter: outgoing breaks into a grid of tiles that fly outward

const ShatterPresenter: React.FC<
  TransitionPresentationComponentProps<{ cols: number; rows: number; seed: string }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { cols, rows, seed } = passedProps;
  const p = presentationProgress;

  // Incoming simply fades in
  if (presentationDirection === "entering") {
    return <AbsoluteFill style={{ opacity: p }}>{children}</AbsoluteFill>;
  }

  // Outgoing: render as cols×rows tiles, each offset by a seeded direction
  const tiles: React.ReactNode[] = [];
  const tileW = 100 / cols;
  const tileH = 100 / rows;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const key = `${c}-${r}`;
      // pseudo-random offsets per tile
      const rng = (n: number) => {
        const x = Math.sin((c + 1) * 127.1 + (r + 1) * 311.7 + n + seed.length) * 43758.5453;
        return x - Math.floor(x);
      };
      const dx = (rng(1) - 0.5) * 2 * 400 * p;
      const dy = (rng(2) - 0.5) * 2 * 400 * p;
      const rot = (rng(3) - 0.5) * 60 * p;
      tiles.push(
        <div
          key={key}
          style={{
            position: "absolute",
            left: `${c * tileW}%`,
            top: `${r * tileH}%`,
            width: `${tileW}%`,
            height: `${tileH}%`,
            overflow: "hidden",
            transform: `translate(${dx}px, ${dy}px) rotate(${rot}deg)`,
            opacity: 1 - p,
          }}
        >
          <div
            style={{
              position: "absolute",
              left: `${-c * 100}%`,
              top: `${-r * 100}%`,
              width: `${cols * 100}%`,
              height: `${rows * 100}%`,
            }}
          >
            {children}
          </div>
        </div>,
      );
    }
  }

  return <AbsoluteFill>{tiles}</AbsoluteFill>;
};

export const shatter = (
  opts: { cols?: number; rows?: number; seed?: string } = {},
): TransitionPresentation<{ cols: number; rows: number; seed: string }> => ({
  component: ShatterPresenter,
  props: { cols: opts.cols ?? 8, rows: opts.rows ?? 5, seed: opts.seed ?? "shatter" },
});

// Morph: scale-dissolve cross-fade with slight blur (fake morph)
// True morph-cut requires feature matching across scenes (ML preprocess).
// This approximation reads well for talking-head/similar-framing transitions.

const MorphPresenter: React.FC<
  TransitionPresentationComponentProps<{ scaleAmt: number; blurPx: number }>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { scaleAmt, blurPx } = passedProps;
  const p = presentationProgress;
  const scale =
    presentationDirection === "entering"
      ? 1 + (1 - p) * scaleAmt
      : 1 - p * scaleAmt;
  const blur = Math.sin(p * Math.PI) * blurPx; // peaks mid-transition
  const style: React.CSSProperties = {
    transform: `scale(${scale})`,
    filter: `blur(${blur}px)`,
    opacity: presentationDirection === "entering" ? p : 1 - p,
  };
  return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
};

export const morph = (
  opts: { scaleAmt?: number; blurPx?: number } = {},
): TransitionPresentation<{ scaleAmt: number; blurPx: number }> => ({
  component: MorphPresenter,
  props: { scaleAmt: opts.scaleAmt ?? 0.08, blurPx: opts.blurPx ?? 8 },
});
