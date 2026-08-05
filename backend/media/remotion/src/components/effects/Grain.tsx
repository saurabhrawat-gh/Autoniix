import React from "react";
import { AbsoluteFill, random, useCurrentFrame } from "remotion";

/**
 * Per-frame SVG noise overlay. Approximates film grain without needing a
 * pre-rendered texture. Intensity controls overall opacity.
 */
export interface GrainProps {
  intensity?: number;
  scale?: number;
}

export const Grain: React.FC<GrainProps> = ({ intensity = 0.08, scale = 0.9 }) => {
  const frame = useCurrentFrame();
  const seed = random(`grain-${frame}`) * 1000;

  const svg = `
    <svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%'>
      <filter id='n'>
        <feTurbulence type='fractalNoise' baseFrequency='${scale}' numOctaves='2' seed='${seed.toFixed(0)}'/>
        <feColorMatrix type='matrix' values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0'/>
      </filter>
      <rect width='100%' height='100%' filter='url(#n)' opacity='1'/>
    </svg>`;
  const uri = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        backgroundImage: uri,
        mixBlendMode: "overlay",
        opacity: intensity,
      }}
    />
  );
};
