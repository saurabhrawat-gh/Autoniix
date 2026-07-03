/**
 * Film Grain Library — 70+ presets
 *
 * Premium-first: Envato grain overlays are primary (50+),
 * RocketStock free supplements fill remaining slots (20).
 *
 * All entries reference files expected in /public/assets/grain/.
 * After downloading assets per ASSET-DOWNLOAD-GUIDE.md, these paths resolve
 * via staticFile() at render time.
 *
 * Grain types:
 *   - 35mm Cinematic (fine/heavy) — modern cinema look
 *   - 16mm Documentary — gritty documentary/indie feel
 *   - 8mm Vintage — warm retro home movie aesthetic
 *   - Super 8 — organic warm 70s texture
 *   - Damaged/Archival — heavy scratches, dust, gate weave
 *   - Film Burns — light exposure burns for transitions
 *   - Clean Subtle — barely-there digital texture
 */

import { staticFile } from "remotion";
import type { AssetEntry } from "../services/assetResolver";
import { registerAssets } from "../services/assetResolver";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface GrainPreset {
  id: string;
  name: string;
  /** Default blend mode for this grain type */
  blendMode: string;
  /** Default opacity 0..1 */
  opacity: number;
  /** Suggested playback rate */
  playbackRate: number;
  /** Source provider */
  source: "envato" | "rocketstock";
  /** Tags for filtering */
  tags: string[];
}

/* ------------------------------------------------------------------ */
/* Envato Premium Grain (50 presets)                                    */
/* ------------------------------------------------------------------ */

const envatoGrain: GrainPreset[] = [
  ...Array.from({ length: 10 }, (_, i) => ({
    id: `grain.envato.35mm_fine_${String(i + 1).padStart(2, "0")}`,
    name: `35mm Cinematic Fine ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.25,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["35mm", "cinematic", "fine", "subtle", "premium"],
  })),

  ...Array.from({ length: 5 }, (_, i) => ({
    id: `grain.envato.35mm_heavy_${String(i + 1).padStart(2, "0")}`,
    name: `35mm Cinematic Heavy ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.35,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["35mm", "cinematic", "heavy", "gritty", "premium"],
  })),

  ...Array.from({ length: 8 }, (_, i) => ({
    id: `grain.envato.16mm_doc_${String(i + 1).padStart(2, "0")}`,
    name: `16mm Documentary ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.30,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["16mm", "documentary", "indie", "gritty", "premium"],
  })),

  ...Array.from({ length: 8 }, (_, i) => ({
    id: `grain.envato.8mm_vintage_${String(i + 1).padStart(2, "0")}`,
    name: `8mm Vintage ${i + 1}`,
    blendMode: "soft-light",
    opacity: 0.40,
    playbackRate: 0.9,
    source: "envato" as const,
    tags: ["8mm", "vintage", "retro", "warm", "premium"],
  })),

  ...Array.from({ length: 5 }, (_, i) => ({
    id: `grain.envato.super8_warm_${String(i + 1).padStart(2, "0")}`,
    name: `Super 8 Warm ${i + 1}`,
    blendMode: "soft-light",
    opacity: 0.38,
    playbackRate: 0.85,
    source: "envato" as const,
    tags: ["super8", "vintage", "warm", "organic", "premium"],
  })),

  ...Array.from({ length: 5 }, (_, i) => ({
    id: `grain.envato.damaged_${String(i + 1).padStart(2, "0")}`,
    name: `Damaged Archival ${i + 1}`,
    blendMode: "screen",
    opacity: 0.45,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["damaged", "archival", "scratches", "dust", "heavy", "premium"],
  })),

  ...Array.from({ length: 5 }, (_, i) => ({
    id: `grain.envato.film_burn_${String(i + 1).padStart(2, "0")}`,
    name: `Film Burn ${i + 1}`,
    blendMode: "screen",
    opacity: 0.50,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["film_burn", "transition", "light", "warm", "premium"],
  })),

  ...Array.from({ length: 4 }, (_, i) => ({
    id: `grain.envato.clean_subtle_${String(i + 1).padStart(2, "0")}`,
    name: `Clean Subtle ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.15,
    playbackRate: 1,
    source: "envato" as const,
    tags: ["clean", "subtle", "minimal", "digital", "premium"],
  })),
];

/* ------------------------------------------------------------------ */
/* RocketStock Free Supplement (20 presets)                             */
/* ------------------------------------------------------------------ */

const rocketstockGrain: GrainPreset[] = [
  ...Array.from({ length: 16 }, (_, i) => ({
    id: `grain.rocketstock.${String(i + 1).padStart(2, "0")}`,
    name: `RocketStock Grain ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.30,
    playbackRate: 1,
    source: "rocketstock" as const,
    tags: ["35mm", "free", "general"],
  })),

  ...Array.from({ length: 4 }, (_, i) => ({
    id: `grain.rocketstock.extra_${String(i + 1).padStart(2, "0")}`,
    name: `RocketStock Grain Extra ${i + 1}`,
    blendMode: "overlay",
    opacity: 0.28,
    playbackRate: 1,
    source: "rocketstock" as const,
    tags: ["general", "free"],
  })),
];

/* ------------------------------------------------------------------ */
/* Combined Library                                                    */
/* ------------------------------------------------------------------ */

export const grainLibrary: GrainPreset[] = [...envatoGrain, ...rocketstockGrain];

/**
 * Resolve a grain preset by ID.
 */
export function resolveGrain(id: string): GrainPreset | null {
  return grainLibrary.find((g) => g.id === id) ?? null;
}

/**
 * Get grain presets by tag.
 */
export function getGrainByTag(tag: string): GrainPreset[] {
  return grainLibrary.filter((g) => g.tags.includes(tag));
}

/**
 * Get a random grain preset, with premium bias.
 */
export function getRandomGrain(tags?: string[]): GrainPreset | null {
  let candidates = grainLibrary;
  if (tags && tags.length > 0) {
    candidates = candidates.filter((g) => tags.some((t) => g.tags.includes(t)));
  }
  if (candidates.length === 0) return null;

  const premium = candidates.filter((g) => g.source === "envato");
  const pool = premium.length > 0 && Math.random() < 0.85 ? premium : candidates;
  return pool[Math.floor(Math.random() * pool.length)] ?? null;
}

/**
 * Build the static file path for a grain preset.
 */
export function grainPath(preset: GrainPreset): string {
  if (preset.source === "envato") {
    const filename = preset.id.replace("grain.envato.", "");
    return staticFile(`assets/grain/envato/${filename}.mp4`);
  }
  if (preset.source === "rocketstock") {
    const filename = preset.id.replace("grain.rocketstock.", "");
    return staticFile(`assets/grain/rocketstock/${filename}.mp4`);
  }
  return "";
}

/* ------------------------------------------------------------------ */
/* Register all grain as generic AssetEntry for the unified resolver   */
/* ------------------------------------------------------------------ */

export function registerGrainAssets(): void {
  const assets: AssetEntry[] = grainLibrary.map((g) => ({
    id: g.id,
    name: g.name,
    category: "grain",
    source: g.source,
    premium: g.source === "envato",
    quality: g.source === "envato" ? 5 : 3,
    path: grainPath(g),
    format: "mp4",
    tags: g.tags,
    meta: {
      blendMode: g.blendMode,
      opacity: g.opacity,
      playbackRate: g.playbackRate,
    },
  }));
  registerAssets(assets);
}
