/**
 * Visual Overlay Library — 50+ presets
 *
 * Premium-first: All from Envato Elements.
 * Overlay types: light leaks, dust particles, bokeh, lens flares,
 * film burns, smoke — composited via CSS blend modes (screen, add).
 *
 * Files expected in /public/assets/overlays/envato/ after downloading
 * per ASSET-DOWNLOAD-GUIDE.md.
 */

import { staticFile } from "remotion";
import type { AssetEntry } from "../services/assetResolver";
import { registerAssets } from "../services/assetResolver";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface OverlayPreset {
  id: string;
  name: string;
  /** Overlay type for grouping */
  type: "light_leak" | "dust" | "bokeh" | "lens_flare" | "film_burn" | "smoke";
  /** Default CSS blend mode */
  blendMode: string;
  /** Default opacity 0..1 */
  opacity: number;
  /** Source provider */
  source: "envato";
  /** Tags for filtering */
  tags: string[];
}

/* ------------------------------------------------------------------ */
/* Helper                                                              */
/* ------------------------------------------------------------------ */

function batch(
  prefix: string,
  namePrefix: string,
  type: OverlayPreset["type"],
  count: number,
  blendMode: string,
  opacity: number,
  tags: string[],
): OverlayPreset[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `overlay.envato.${prefix}_${String(i + 1).padStart(2, "0")}`,
    name: `${namePrefix} ${i + 1}`,
    type,
    blendMode,
    opacity,
    source: "envato" as const,
    tags: [...tags, "premium"],
  }));
}

/* ------------------------------------------------------------------ */
/* Envato Premium Overlays (52 presets)                                 */
/* ------------------------------------------------------------------ */

const overlayPresets: OverlayPreset[] = [
  ...batch("light_leak_warm", "Light Leak Warm", "light_leak", 8, "screen", 0.45, ["light_leak", "warm", "organic"]),

  ...batch("light_leak_cool", "Light Leak Cool", "light_leak", 5, "screen", 0.40, ["light_leak", "cool", "blue"]),

  ...batch("light_leak_anamorphic", "Anamorphic Flare", "light_leak", 5, "screen", 0.35, ["light_leak", "anamorphic", "cinematic", "horizontal"]),

  ...batch("dust_particles", "Dust Particles", "dust", 8, "screen", 0.30, ["dust", "particles", "floating", "ambient"]),

  ...batch("bokeh", "Bokeh", "bokeh", 8, "screen", 0.35, ["bokeh", "soft", "dreamy", "depth"]),

  ...batch("lens_flare", "Lens Flare", "lens_flare", 8, "screen", 0.40, ["lens_flare", "flare", "cinematic", "bright"]),

  ...batch("film_burn", "Film Burn", "film_burn", 5, "screen", 0.50, ["film_burn", "transition", "light", "analog"]),

  ...batch("smoke", "Smoke", "smoke", 5, "screen", 0.25, ["smoke", "haze", "atmosphere", "moody"]),
];

/* ------------------------------------------------------------------ */
/* Combined Library                                                    */
/* ------------------------------------------------------------------ */

export const overlayLibrary: OverlayPreset[] = overlayPresets;

/**
 * Resolve an overlay preset by ID.
 */
export function resolveOverlay(id: string): OverlayPreset | null {
  return overlayLibrary.find((o) => o.id === id) ?? null;
}

/**
 * Get overlays by type.
 */
export function getOverlaysByType(type: OverlayPreset["type"]): OverlayPreset[] {
  return overlayLibrary.filter((o) => o.type === type);
}

/**
 * Get overlays by tag.
 */
export function getOverlaysByTag(tag: string): OverlayPreset[] {
  return overlayLibrary.filter((o) => o.tags.includes(tag));
}

/**
 * Get a random overlay, optionally filtered by type.
 */
export function getRandomOverlay(type?: OverlayPreset["type"]): OverlayPreset | null {
  let candidates = overlayLibrary;
  if (type) candidates = candidates.filter((o) => o.type === type);
  if (candidates.length === 0) return null;
  return candidates[Math.floor(Math.random() * candidates.length)] ?? null;
}

/**
 * Build the static file path for an overlay preset.
 */
export function overlayPath(preset: OverlayPreset): string {
  const filename = preset.id.replace("overlay.envato.", "");
  return staticFile(`assets/overlays/envato/${filename}.mp4`);
}

/* ------------------------------------------------------------------ */
/* Register all overlays as AssetEntry for the unified resolver        */
/* ------------------------------------------------------------------ */

export function registerOverlayAssets(): void {
  const assets: AssetEntry[] = overlayLibrary.map((o) => ({
    id: o.id,
    name: o.name,
    category: "overlay" as const,
    source: o.source,
    premium: true,
    quality: 5,
    path: overlayPath(o),
    format: "mp4",
    tags: o.tags,
    meta: { blendMode: o.blendMode, opacity: o.opacity, overlayType: o.type },
  }));
  registerAssets(assets);
}
