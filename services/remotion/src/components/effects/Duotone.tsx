import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Duotone: map grayscale output to a two-color gradient. Accepts children;
 * applies an SVG filter + feComponentTransfer to remap luminance.
 */
export interface DuotoneProps {
  shadow?: string;
  highlight?: string;
  children?: React.ReactNode;
}

const hexToRgb = (hex: string): [number, number, number] => {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const num = parseInt(n, 16);
  return [(num >> 16) & 0xff, (num >> 8) & 0xff, num & 0xff];
};

export const Duotone: React.FC<DuotoneProps> = ({
  shadow = "#1b1e3f",
  highlight = "#ff3b30",
  children,
}) => {
  const [sr, sg, sb] = hexToRgb(shadow).map((n) => (n / 255).toFixed(3));
  const [hr, hg, hb] = hexToRgb(highlight).map((n) => (n / 255).toFixed(3));
  const id = `dt-${shadow}-${highlight}`.replace(/#/g, "");

  const svg = `
    <svg xmlns='http://www.w3.org/2000/svg'>
      <filter id='${id}'>
        <feColorMatrix type='matrix' values='
          0.33 0.33 0.33 0 0
          0.33 0.33 0.33 0 0
          0.33 0.33 0.33 0 0
          0 0 0 1 0' />
        <feComponentTransfer>
          <feFuncR tableValues='${sr} ${hr}' type='table' />
          <feFuncG tableValues='${sg} ${hg}' type='table' />
          <feFuncB tableValues='${sb} ${hb}' type='table' />
        </feComponentTransfer>
      </filter>
    </svg>`;
  const filterUrl = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}#${id}")`;

  if (!children) {
    return <AbsoluteFill style={{ pointerEvents: "none", backdropFilter: filterUrl }} />;
  }
  return <AbsoluteFill style={{ filter: filterUrl }}>{children}</AbsoluteFill>;
};
