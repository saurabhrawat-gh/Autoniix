/**
 * Per-clip capability tagging for the tier router (see 02-FUTURE-ENGINE-ARCHITECTURE.md §2.4).
 *
 * Tier 0 — WebGPU compositor (shader-pure scenes)
 * Tier 1 — Chromium (React-general, safe fallback)
 * Tier 2 — ffmpeg-direct (stock-only montage segments)
 *
 * At P0 we only emit tags. The router in P1 consumes them to pick a worker
 * queue. Today every clip is effectively Tier-1, so the default tag is
 * `requires_react: true`.
 */

import type { Clip, SceneClip, SceneGraph } from "./types";

export type ClipCapability = {
  requiresReact: boolean;
  requiresDom: boolean;
  requiresWebgl: boolean;
  stockOnly: boolean;
  shaderPure: boolean;
};

export type ClipCapabilityTagged = { clipId: string; trackId: string; tier: "t0" | "t1" | "t2"; caps: ClipCapability };

/**
 * Conservative initial tagging:
 *   - StockFootageScene with no overlays/effects → Tier 2
 *   - Scenes in the SHADER_PURE_SCENES set AND no overlays → Tier 0
 *   - Everything else → Tier 1
 */
const SHADER_PURE_SCENES = new Set<string>([
  "KineticTypography",
  "AdvancedKineticText",
  "TextStrokeReveal",
  "FullScreenText",
]);

const STOCK_SCENES = new Set<string>(["StockFootageScene"]);

const DOM_HEAVY_SCENES = new Set<string>(["CodeTyping", "BrowserMockup", "SocialMockup", "PhoneMockup"]);

export function tagCapabilities(graph: SceneGraph): ClipCapabilityTagged[] {
  const out: ClipCapabilityTagged[] = [];
  for (const track of graph.tracks) {
    for (const clip of track.clips) {
      const caps = clipCapability(clip);
      const tier = chooseTier(caps);
      out.push({ clipId: clip.id, trackId: track.id, tier, caps });
    }
  }
  return out;
}

function clipCapability(clip: Clip): ClipCapability {
  if (clip.kind !== "scene") {
    return { requiresReact: true, requiresDom: false, requiresWebgl: false, stockOnly: false, shaderPure: false };
  }
  const s = clip as SceneClip;
  const hasOverlays = (s.overlays?.length ?? 0) > 0;
  const hasEffects = (s.effects?.length ?? 0) > 0;
  const hasAnimIn = (s.animationsIn?.length ?? 0) > 0;
  const hasAnimOut = (s.animationsOut?.length ?? 0) > 0;
  const hasAnims = hasAnimIn || hasAnimOut;

  if (STOCK_SCENES.has(s.scenePreset) && !hasOverlays && !hasEffects && !hasAnims) {
    return { requiresReact: false, requiresDom: false, requiresWebgl: false, stockOnly: true, shaderPure: false };
  }
  if (SHADER_PURE_SCENES.has(s.scenePreset) && !hasOverlays) {
    return { requiresReact: false, requiresDom: false, requiresWebgl: true, stockOnly: false, shaderPure: true };
  }
  return {
    requiresReact: true,
    requiresDom: DOM_HEAVY_SCENES.has(s.scenePreset),
    requiresWebgl: false,
    stockOnly: false,
    shaderPure: false,
  };
}

function chooseTier(caps: ClipCapability): "t0" | "t1" | "t2" {
  if (caps.stockOnly) return "t2";
  if (caps.shaderPure) return "t0";
  return "t1";
}
