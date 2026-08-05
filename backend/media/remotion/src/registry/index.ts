import { SCENE_PRESETS } from "./scenes";
import { TRANSITION_PRESETS, resolveTransition } from "./transitions";
import { ANIMATION_PRESETS } from "./animations";
import { EFFECT_PRESETS } from "./effects";
import { OVERLAY_PRESETS } from "./overlays";
import { SFX_LIBRARY, resolveSfx, listSfx, sfxCount, listSfxPremiumFirst, listSfxBySource } from "./sfxLibrary";
import { grainLibrary, resolveGrain, getGrainByTag, getRandomGrain, grainPath, registerGrainAssets } from "./grainLibrary";
import { lutLibrary, resolveLUT, getLUTsByCategory, getLUTsByTag, getRandomLUT, lutPath, registerLutAssets } from "./lutLibrary";
import { overlayLibrary, resolveOverlay, getOverlaysByType, getOverlaysByTag, getRandomOverlay, overlayPath, registerOverlayAssets } from "./overlayLibrary";
import { resolveAsset, resolveAssetById, resolveRandom, getAssetStats, getAssetCount } from "../services/assetResolver";
import type { PresetCategory, PresetEntry, PresetRegistry } from "./types";
import type { TransitionPresetEntry } from "./transitionTypes";
import type { SfxEntry, SfxCategory, SfxSource } from "./sfxLibrary";
import type { AssetEntry, AssetCategory, ResolveResult } from "../services/assetResolver";

export {
  SCENE_PRESETS,
  TRANSITION_PRESETS,
  ANIMATION_PRESETS,
  EFFECT_PRESETS,
  OVERLAY_PRESETS,
  SFX_LIBRARY,
  resolveTransition,
  resolveSfx,
  listSfx,
  sfxCount,
  listSfxPremiumFirst,
  listSfxBySource,
  grainLibrary,
  resolveGrain,
  getGrainByTag,
  getRandomGrain,
  grainPath,
  registerGrainAssets,
  lutLibrary,
  resolveLUT,
  getLUTsByCategory,
  getLUTsByTag,
  getRandomLUT,
  lutPath,
  registerLutAssets,
  overlayLibrary,
  resolveOverlay,
  getOverlaysByType,
  getOverlaysByTag,
  getRandomOverlay,
  overlayPath,
  registerOverlayAssets,
  resolveAsset,
  resolveAssetById,
  resolveRandom,
  getAssetStats,
  getAssetCount,
};
export type { TransitionPresetEntry, SfxEntry, SfxCategory, SfxSource, AssetEntry, AssetCategory, ResolveResult };

/**
 * Unified map for component-style presets (scenes, animations, effects, overlays).
 * Transitions are NOT included here — their shape differs (see transitionTypes.ts)
 * and they must be resolved via `resolveTransition(id)`.
 */
export const ALL_PRESETS: PresetRegistry = {
  ...SCENE_PRESETS,
  ...ANIMATION_PRESETS,
  ...EFFECT_PRESETS,
  ...OVERLAY_PRESETS,
};

export function resolvePreset(
  id: string,
  overrides: Record<string, unknown> = {},
): { Component: PresetEntry["component"]; props: Record<string, unknown>; meta: { category: PresetCategory; tags: string[] } } | null {
  const entry = ALL_PRESETS[id];
  if (!entry) return null;
  return {
    Component: entry.component,
    props: { ...entry.defaultProps, ...overrides },
    meta: { category: entry.category, tags: entry.tags },
  };
}

export function listPresets(filter?: { category?: PresetCategory; tag?: string }): PresetEntry[] {
  return Object.values(ALL_PRESETS).filter((p) => {
    if (filter?.category && p.category !== filter.category) return false;
    if (filter?.tag && !p.tags.includes(filter.tag)) return false;
    return true;
  });
}

export type { PresetCategory, PresetEntry, PresetRegistry };

/**
 * Initialize all asset registries (call once at app startup).
 * Registers grain, LUT, and overlay assets into the unified resolver.
 */
export function initAssetRegistries(): void {
  registerGrainAssets();
  registerLutAssets();
  registerOverlayAssets();
}
