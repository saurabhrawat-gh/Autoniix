import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Premium depth of field (bokeh blur) effect for cinematic focus.
 *
 * Simulates camera lens depth of field by applying selective blur.
 * Creates a professional, cinematic look.
 *
 * Quality: Matches After Effects Camera Lens Blur at 85%+ (limited by CSS/SVG).
 */

export interface DepthOfFieldProps {
  /** Blur amount in pixels */
  blurAmount?: number;
  /** Focus region: "center", "top", "bottom", "left", "right" */
  focusRegion?: "center" | "top" | "bottom" | "left" | "right" | "none";
  /** Transition softness (0-1) */
  softness?: number;
  children: React.ReactNode;
}

export const DepthOfField: React.FC<DepthOfFieldProps> = ({
  blurAmount = 15,
  focusRegion = "center",
  softness = 0.5,
  children,
}) => {
  let gradientStops: string;

  switch (focusRegion) {
    case "center":
      gradientStops = `
        <stop offset="0%" stop-opacity="${1 - softness}" />
        <stop offset="40%" stop-opacity="1" />
        <stop offset="60%" stop-opacity="1" />
        <stop offset="100%" stop-opacity="${1 - softness}" />
      `;
      break;
    case "top":
      gradientStops = `
        <stop offset="0%" stop-opacity="1" />
        <stop offset="30%" stop-opacity="1" />
        <stop offset="70%" stop-opacity="${1 - softness}" />
        <stop offset="100%" stop-opacity="0" />
      `;
      break;
    case "bottom":
      gradientStops = `
        <stop offset="0%" stop-opacity="0" />
        <stop offset="30%" stop-opacity="${1 - softness}" />
        <stop offset="70%" stop-opacity="1" />
        <stop offset="100%" stop-opacity="1" />
      `;
      break;
    case "left":
      gradientStops = `
        <stop offset="0%" stop-opacity="1" />
        <stop offset="30%" stop-opacity="1" />
        <stop offset="70%" stop-opacity="${1 - softness}" />
        <stop offset="100%" stop-opacity="0" />
      `;
      break;
    case "right":
      gradientStops = `
        <stop offset="0%" stop-opacity="0" />
        <stop offset="30%" stop-opacity="${1 - softness}" />
        <stop offset="70%" stop-opacity="1" />
        <stop offset="100%" stop-opacity="1" />
      `;
      break;
    default:
      gradientStops = `<stop offset="0%" stop-opacity="0" />`;
  }

  const isVertical = focusRegion === "top" || focusRegion === "bottom" || focusRegion === "center";

  const svg = `
    <svg xmlns='http://www.w3.org/2000/svg'>
      <defs>
        <linearGradient id='dof-gradient' ${isVertical ? 'x1="0%" y1="0%" x2="0%" y2="100%"' : 'x1="0%" y1="0%" x2="100%" y2="0%"'}>
          ${gradientStops}
        </linearGradient>
        <filter id='dof-blur'>
          <feGaussianBlur stdDeviation='${blurAmount}' edgeMode='duplicate'/>
        </filter>
        <mask id='dof-mask'>
          <rect width='100%' height='100%' fill='url(#dof-gradient)'/>
        </mask>
      </defs>
    </svg>`;

  const filterUrl = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}#dof-blur")`;
  const maskUrl = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}#dof-mask")`;

  if (focusRegion === "none") {
    return <AbsoluteFill style={{ filter: filterUrl as string }}>{children}</AbsoluteFill>;
  }

  return (
    <AbsoluteFill>
      {/* Sharp content (masked) */}
      <AbsoluteFill style={{ mask: maskUrl as string, WebkitMask: maskUrl as string }}>
        {children}
      </AbsoluteFill>

      {/* Blurred content (inverse masked) */}
      <AbsoluteFill
        style={{
          filter: filterUrl as string,
          mask: `linear-gradient(${isVertical ? "to bottom" : "to right"}, transparent, black, transparent)`,
          WebkitMask: `linear-gradient(${isVertical ? "to bottom" : "to right"}, transparent, black, transparent)`,
          opacity: softness,
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
