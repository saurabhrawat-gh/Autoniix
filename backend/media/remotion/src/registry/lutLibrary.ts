/**
 * LUT Library — 215+ color grading presets
 *
 * Premium-first: Envato LUTs (150+) are primary.
 * Free supplements: RocketStock (35), Lutify.me (10), SmallHD (20).
 *
 * Files expected in /public/assets/luts/ after downloading per ASSET-DOWNLOAD-GUIDE.md.
 *
 * Categories:
 *   - Cinematic — teal/orange, blockbuster, moody
 *   - Film Emulation — Kodak, Fuji, Ilford stock emulations
 *   - Documentary — natural, clean, broadcast-ready
 *   - Commercial — bright, vibrant, corporate
 *   - Vintage — faded, retro, 70s/80s
 *   - Moody/Dark — desaturated, noir, cold
 *   - Warm — golden hour, wedding, sunset
 *   - HDR — vivid, punchy, high-contrast
 */

import { staticFile } from "remotion";
import type { AssetEntry } from "../services/assetResolver";
import { registerAssets } from "../services/assetResolver";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface LUTPreset {
  id: string;
  name: string;
  /** LUT category for grouping */
  category: string;
  /** Default intensity 0..1 */
  intensity: number;
  /** Source provider */
  source: "envato" | "rocketstock" | "lutify" | "smallhd";
  /** Tags for filtering */
  tags: string[];
}

/* ------------------------------------------------------------------ */
/* Helper: generate preset batch                                       */
/* ------------------------------------------------------------------ */

function batch(
  prefix: string,
  namePrefix: string,
  category: string,
  count: number,
  source: "envato" | "rocketstock" | "lutify" | "smallhd",
  intensity: number,
  tags: string[],
): LUTPreset[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `lut.${source}.${prefix}_${String(i + 1).padStart(2, "0")}`,
    name: `${namePrefix} ${i + 1}`,
    category,
    intensity,
    source,
    tags: [...tags, source === "envato" ? "premium" : "free"],
  }));
}

/* ------------------------------------------------------------------ */
/* Envato Premium LUTs (150 presets)                                   */
/* ------------------------------------------------------------------ */

const envatoLuts: LUTPreset[] = [
  ...batch("cinematic_teal_orange", "Cinematic Teal Orange", "cinematic", 10, "envato", 0.85, ["cinematic", "teal_orange", "blockbuster"]),
  ...batch("cinematic_cool", "Cinematic Cool", "cinematic", 10, "envato", 0.80, ["cinematic", "cool", "blue"]),
  ...batch("cinematic_warm", "Cinematic Warm", "cinematic", 10, "envato", 0.80, ["cinematic", "warm", "golden"]),

  ...batch("kodak_2383", "Kodak 2383 Print", "film_emulation", 5, "envato", 0.90, ["film", "kodak", "print", "cinema"]),
  ...batch("kodak_5219", "Kodak 5219 Negative", "film_emulation", 5, "envato", 0.85, ["film", "kodak", "negative"]),
  ...batch("fuji_3510", "Fuji 3510 Print", "film_emulation", 5, "envato", 0.90, ["film", "fuji", "print"]),
  ...batch("ilford_hp5", "Ilford HP5 BW", "film_emulation", 5, "envato", 0.80, ["film", "ilford", "bw", "monochrome"]),

  ...batch("moody_dark", "Moody Dark", "moody", 8, "envato", 0.75, ["moody", "dark", "desaturated"]),
  ...batch("moody_noir", "Noir", "moody", 4, "envato", 0.70, ["moody", "noir", "contrast"]),
  ...batch("moody_cold", "Cold Moody", "moody", 3, "envato", 0.75, ["moody", "cold", "blue"]),

  ...batch("doc_natural", "Documentary Natural", "documentary", 8, "envato", 0.70, ["documentary", "natural", "clean"]),
  ...batch("doc_broadcast", "Broadcast Ready", "documentary", 7, "envato", 0.65, ["documentary", "broadcast", "neutral"]),

  ...batch("commercial_bright", "Commercial Bright", "commercial", 8, "envato", 0.70, ["commercial", "bright", "vibrant"]),
  ...batch("commercial_clean", "Commercial Clean", "commercial", 7, "envato", 0.65, ["commercial", "clean", "corporate"]),

  ...batch("vintage_faded", "Vintage Faded", "vintage", 8, "envato", 0.75, ["vintage", "faded", "retro"]),
  ...batch("vintage_70s", "70s Film Look", "vintage", 4, "envato", 0.80, ["vintage", "70s", "warm"]),
  ...batch("vintage_polaroid", "Polaroid Style", "vintage", 3, "envato", 0.70, ["vintage", "polaroid", "instant"]),

  ...batch("warm_golden_hour", "Golden Hour", "warm", 5, "envato", 0.75, ["warm", "golden", "sunset"]),
  ...batch("warm_wedding", "Wedding Warm", "warm", 5, "envato", 0.70, ["warm", "wedding", "soft"]),

  ...batch("hdr_vivid", "HDR Vivid", "hdr", 5, "envato", 0.60, ["hdr", "vivid", "punchy"]),
  ...batch("hdr_contrast", "HDR High Contrast", "hdr", 5, "envato", 0.65, ["hdr", "contrast", "saturated"]),

  ...batch("travel_tropical", "Travel Tropical", "travel", 5, "envato", 0.70, ["travel", "tropical", "vibrant"]),
  ...batch("travel_urban", "Travel Urban", "travel", 5, "envato", 0.70, ["travel", "urban", "city"]),

  ...batch("bw_classic", "B&W Classic", "bw", 5, "envato", 0.90, ["bw", "monochrome", "classic"]),
  ...batch("bw_high_contrast", "B&W High Contrast", "bw", 5, "envato", 0.85, ["bw", "monochrome", "contrast"]),
];

/* ------------------------------------------------------------------ */
/* Free Supplement LUTs (65 presets)                                   */
/* ------------------------------------------------------------------ */

const rocketstockLuts: LUTPreset[] = batch(
  "rs", "RocketStock", "cinematic", 35, "rocketstock", 0.75,
  ["cinematic", "general"],
);

const lutifyLuts: LUTPreset[] = batch(
  "lutify", "Lutify.me", "cinematic", 10, "lutify", 0.75,
  ["cinematic", "film"],
);

const smallhdLuts: LUTPreset[] = batch(
  "movie", "SmallHD Movie", "film_emulation", 20, "smallhd", 0.80,
  ["film", "movie", "cinema"],
);

/* ------------------------------------------------------------------ */
/* Combined Library                                                    */
/* ------------------------------------------------------------------ */

export const lutLibrary: LUTPreset[] = [
  ...envatoLuts,
  ...rocketstockLuts,
  ...lutifyLuts,
  ...smallhdLuts,
];

/**
 * Resolve a LUT preset by ID.
 */
export function resolveLUT(id: string): LUTPreset | null {
  return lutLibrary.find((l) => l.id === id) ?? null;
}

/**
 * Get LUT presets by category.
 */
export function getLUTsByCategory(category: string): LUTPreset[] {
  return lutLibrary.filter((l) => l.category === category);
}

/**
 * Get LUT presets by tag.
 */
export function getLUTsByTag(tag: string): LUTPreset[] {
  return lutLibrary.filter((l) => l.tags.includes(tag));
}

/**
 * Get a random LUT, with premium bias.
 */
export function getRandomLUT(category?: string): LUTPreset | null {
  let candidates = lutLibrary;
  if (category) {
    candidates = candidates.filter((l) => l.category === category);
  }
  if (candidates.length === 0) return null;

  const premium = candidates.filter((l) => l.source === "envato");
  const pool = premium.length > 0 && Math.random() < 0.85 ? premium : candidates;
  return pool[Math.floor(Math.random() * pool.length)] ?? null;
}

/**
 * Build the static file path for a LUT preset.
 */
export function lutPath(preset: LUTPreset): string {
  const filename = preset.id.replace(`lut.${preset.source}.`, "");
  return staticFile(`assets/luts/${preset.source}/${filename}.cube`);
}

/* ------------------------------------------------------------------ */
/* Register all LUTs as AssetEntry for the unified resolver            */
/* ------------------------------------------------------------------ */

export function registerLutAssets(): void {
  const assets: AssetEntry[] = lutLibrary.map((l) => ({
    id: l.id,
    name: l.name,
    category: "lut" as const,
    source: l.source,
    premium: l.source === "envato",
    quality: l.source === "envato" ? 5 : l.source === "smallhd" ? 4 : 3,
    path: lutPath(l),
    format: "cube",
    tags: l.tags,
    meta: { intensity: l.intensity, lutCategory: l.category },
  }));
  registerAssets(assets);
}
