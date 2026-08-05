/**
 * Premium-First Asset Resolver
 *
 * Central service for resolving asset references to actual file paths/URLs.
 * Implements the premium-first strategy defined in ASSET-STRATEGY.md:
 *
 *   1. Check Envato premium assets FIRST
 *   2. Fall back to curated free supplements ONLY if no premium match
 *   3. Procedural/built-in fallback as last resort
 *
 * Supports: grain, luts, overlays, sfx, music, fonts
 */

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type AssetCategory = "grain" | "lut" | "overlay" | "sfx" | "music" | "font";

export type AssetSource = "envato" | "rocketstock" | "lutify" | "smallhd" | "mixkit" | "pixabay" | "freesound" | "youtube_library" | "google" | "storyset" | "built_in";

export interface AssetEntry {
  /** Unique ID, e.g. "grain.envato.35mm_fine_01" */
  id: string;
  /** Human-readable name */
  name: string;
  /** Asset category */
  category: AssetCategory;
  /** Source provider */
  source: AssetSource;
  /** Whether this is a premium (paid) asset */
  premium: boolean;
  /** Quality rating 1-5 stars */
  quality: number;
  /** Resolved file path or URL */
  path: string;
  /** File format (mp4, wav, cube, otf, etc.) */
  format: string;
  /** Optional tags for search/filter */
  tags?: string[];
  /** Optional metadata */
  meta?: Record<string, unknown>;
}

export interface ResolveResult {
  asset: AssetEntry;
  /** How it was resolved */
  resolution: "premium" | "free_supplement" | "built_in";
}

/* ------------------------------------------------------------------ */
/* Asset Registry (in-memory store)                                    */
/* ------------------------------------------------------------------ */

const registry = new Map<string, AssetEntry>();
const categoryIndex = new Map<AssetCategory, AssetEntry[]>();
const tagIndex = new Map<string, AssetEntry[]>();

/**
 * Register an asset in the resolver.
 */
export function registerAsset(asset: AssetEntry): void {
  registry.set(asset.id, asset);

  const catList = categoryIndex.get(asset.category) ?? [];
  catList.push(asset);
  categoryIndex.set(asset.category, catList);

  for (const tag of asset.tags ?? []) {
    const tagList = tagIndex.get(tag) ?? [];
    tagList.push(asset);
    tagIndex.set(tag, tagList);
  }
}

/**
 * Register multiple assets at once.
 */
export function registerAssets(assets: AssetEntry[]): void {
  for (const a of assets) registerAsset(a);
}

/* ------------------------------------------------------------------ */
/* Resolution Logic (Premium-First)                                    */
/* ------------------------------------------------------------------ */

/**
 * Resolve an asset by exact ID.
 */
export function resolveAssetById(id: string): AssetEntry | null {
  return registry.get(id) ?? null;
}

/**
 * Resolve the best asset for a category + tag query.
 * Premium assets are always preferred over free ones.
 * Within each tier, highest quality rating wins.
 */
export function resolveAsset(
  category: AssetCategory,
  tags: string[] = [],
  preferredSource?: AssetSource,
): ResolveResult | null {
  let candidates = categoryIndex.get(category) ?? [];

  if (tags.length > 0) {
    candidates = candidates.filter((a) =>
      tags.some((t) => a.tags?.includes(t)),
    );
  }

  if (preferredSource) {
    const sourceFiltered = candidates.filter((a) => a.source === preferredSource);
    if (sourceFiltered.length > 0) {
      candidates = sourceFiltered;
    }
  }

  if (candidates.length === 0) return null;

  const sorted = [...candidates].sort((a, b) => {
    if (a.premium && !b.premium) return -1;
    if (!a.premium && b.premium) return 1;
    return b.quality - a.quality;
  });

  const best = sorted[0];
  if (!best) return null;
  const resolution: ResolveResult["resolution"] = best.premium
    ? "premium"
    : best.source === "built_in"
      ? "built_in"
      : "free_supplement";

  return { asset: best, resolution };
}

/**
 * Resolve multiple assets (e.g., for building a playlist or overlay stack).
 * Returns up to `limit` assets, premium-first sorted.
 */
export function resolveAssets(
  category: AssetCategory,
  tags: string[] = [],
  limit: number = 10,
): AssetEntry[] {
  let candidates = categoryIndex.get(category) ?? [];

  if (tags.length > 0) {
    candidates = candidates.filter((a) =>
      tags.some((t) => a.tags?.includes(t)),
    );
  }

  const sorted = [...candidates].sort((a, b) => {
    if (a.premium && !b.premium) return -1;
    if (!a.premium && b.premium) return 1;
    return b.quality - a.quality;
  });

  return sorted.slice(0, limit);
}

/**
 * Get a random asset from a category/tag, with premium bias.
 * 80% chance of picking a premium asset, 20% free (if available).
 */
export function resolveRandom(
  category: AssetCategory,
  tags: string[] = [],
): AssetEntry | null {
  let candidates = categoryIndex.get(category) ?? [];

  if (tags.length > 0) {
    candidates = candidates.filter((a) =>
      tags.some((t) => a.tags?.includes(t)),
    );
  }

  if (candidates.length === 0) return null;

  const premium = candidates.filter((a) => a.premium);
  const free = candidates.filter((a) => !a.premium);

  const pool = premium.length > 0 && (free.length === 0 || Math.random() < 0.8)
    ? premium
    : free.length > 0
      ? free
      : premium;

  return pool[Math.floor(Math.random() * pool.length)] ?? null;
}

/* ------------------------------------------------------------------ */
/* Query Helpers                                                       */
/* ------------------------------------------------------------------ */

/**
 * Get all assets in a category.
 */
export function getAssetsByCategory(category: AssetCategory): AssetEntry[] {
  return categoryIndex.get(category) ?? [];
}

/**
 * Get all assets matching a tag.
 */
export function getAssetsByTag(tag: string): AssetEntry[] {
  return tagIndex.get(tag) ?? [];
}

/**
 * Get total asset count, optionally filtered by category.
 */
export function getAssetCount(category?: AssetCategory): number {
  if (category) return (categoryIndex.get(category) ?? []).length;
  return registry.size;
}

/**
 * Get breakdown of premium vs free assets.
 */
export function getAssetStats(): {
  total: number;
  premium: number;
  free: number;
  byCategory: Record<string, { total: number; premium: number; free: number }>;
} {
  let premium = 0;
  let free = 0;
  const byCategory: Record<string, { total: number; premium: number; free: number }> = {};

  for (const [cat, assets] of categoryIndex) {
    const p = assets.filter((a) => a.premium).length;
    const f = assets.length - p;
    byCategory[cat] = { total: assets.length, premium: p, free: f };
    premium += p;
    free += f;
  }

  return { total: registry.size, premium, free, byCategory };
}
