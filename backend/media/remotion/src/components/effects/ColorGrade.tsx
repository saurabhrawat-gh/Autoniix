import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * Named LUT-like CSS filter recipes. CSS `filter` is a fast approximation;
 * real LUT-based grading (via WebGL shader) is Phase 3.
 */
export type GradeLut =
  | "natural_cinematic"
  | "cinematic_teal_orange"
  | "bright_flat"
  | "moody_cool"
  | "noir_bw"
  | "warm_sunset"
  | "cold_winter"
  | "vintage_faded"
  | "neon_night"
  | "high_key_commercial"
  | "matrix_green"
  | "pastel_soft"
  | "hdr_pop"
  | "sepia_doc"
  | "cyberpunk_magenta";

const FILTERS: Record<GradeLut, string> = {
  natural_cinematic: "contrast(1.08) saturate(1.05) brightness(0.98)",
  cinematic_teal_orange: "contrast(1.15) saturate(1.25) hue-rotate(-8deg) brightness(0.97)",
  bright_flat: "contrast(0.95) saturate(1.1) brightness(1.08)",
  moody_cool: "contrast(1.1) saturate(0.85) hue-rotate(10deg) brightness(0.9)",
  noir_bw: "grayscale(1) contrast(1.2) brightness(0.95)",

  warm_sunset: "contrast(1.1) saturate(1.25) hue-rotate(-15deg) brightness(1.02) sepia(0.15)",
  cold_winter: "contrast(1.05) saturate(0.8) hue-rotate(15deg) brightness(1.05)",
  vintage_faded: "contrast(0.85) saturate(0.7) brightness(1.05) sepia(0.35)",
  neon_night: "contrast(1.3) saturate(1.5) brightness(0.9)",
  high_key_commercial: "contrast(0.9) saturate(1.15) brightness(1.15)",
  matrix_green: "contrast(1.2) saturate(1.4) hue-rotate(80deg) brightness(0.95)",
  pastel_soft: "contrast(0.9) saturate(0.85) brightness(1.1)",
  hdr_pop: "contrast(1.25) saturate(1.35) brightness(1.02)",
  sepia_doc: "sepia(0.8) contrast(1.05) brightness(0.98)",
  cyberpunk_magenta: "contrast(1.2) saturate(1.45) hue-rotate(-30deg) brightness(0.95)",
};

export interface ColorGradeProps {
  lut?: GradeLut;
  children?: React.ReactNode;
}

export const ColorGrade: React.FC<ColorGradeProps> = ({ lut = "natural_cinematic", children }) => {
  return <AbsoluteFill style={{ filter: FILTERS[lut] }}>{children}</AbsoluteFill>;
};
