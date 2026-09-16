/**
 * Phase 1E — Per-clip cache key derivation.
 *
 * Reduces a clip's Phase-1A/1B/1C/1D fields to four sha256 fingerprints that
 * index `clip_render_cache`. The diff cache layer in the renderer probes
 * these to skip re-rendering shards whose advanced-editing inputs haven't
 * changed.
 *
 * Hashing rules:
 *   • Each helper returns `null` when the corresponding feature is absent —
 *     null is encoded as SQL NULL (the partial indexes skip null rows).
 *   • Hashes are computed on canonicalized JSON via the existing `hashNode`,
 *     so the result is stable across platforms.
 */

import type { Clip } from "./types";
import { hashNode } from "./hash";

/* ----- Phase 1A — blend mode + opacity ------------------------------- */
export function blendModeHash(clip: Clip): string | null {
  if (clip.kind === "transition") return null;
  const c = (clip as { compositing?: unknown }).compositing;
  if (!c) return null;
  return hashNode(c);
}

/* ----- Phase 1B — advanced text animations --------------------------- */
export function textAnimHash(clip: Clip): string | null {
  if (clip.kind !== "scene") return null;
  const sc = clip as Extract<Clip, { kind: "scene" }>;
  const inAnims = sc.animationsIn ?? [];
  const outAnims = sc.animationsOut ?? [];
  const textPrefixes = ["anim.text.", "anim.in.typewriter", "anim.in.scramble"];
  const isTextAnim = (preset: string): boolean => textPrefixes.some((p) => preset.startsWith(p));
  const items = [...inAnims, ...outAnims].filter((a) => isTextAnim(a.preset));
  if (items.length === 0) return null;
  return hashNode({ items });
}

/* ----- Phase 1C — animated masks ------------------------------------- */
export function maskHash(clip: Clip): string | null {
  if (clip.kind === "transition") return null;
  const masks = (clip as { masks?: unknown }).masks;
  if (!Array.isArray(masks) || masks.length === 0) return null;
  return hashNode(masks);
}

/* ----- Phase 1D — color grade ---------------------------------------- */
export function colorGradeHash(clip: Clip): string | null {
  if (clip.kind !== "scene" && clip.kind !== "stock") return null;
  const grade = (clip as { colorGradeTrack?: unknown }).colorGradeTrack;
  if (!grade) return null;
  return hashNode(grade);
}

/* --------------------------------------------------------------------- */
/* Aggregate                                                             */
/* --------------------------------------------------------------------- */

export interface ClipCacheKeys {
  clipId: string;
  blendMode: string | null;
  blendModeHash: string | null;
  maskCount: number;
  maskHash: string | null;
  colorGradeHash: string | null;
  textAnimHash: string | null;
}

export function clipCacheKeys(clip: Clip): ClipCacheKeys {
  if (clip.kind === "transition") {
    return {
      clipId: clip.id,
      blendMode: null,
      blendModeHash: null,
      maskCount: 0,
      maskHash: null,
      colorGradeHash: null,
      textAnimHash: null,
    };
  }
  const compositing = (clip as { compositing?: { blendMode?: string } }).compositing;
  const masks = (clip as { masks?: unknown[] }).masks ?? [];
  return {
    clipId: clip.id,
    blendMode: compositing?.blendMode ?? null,
    blendModeHash: blendModeHash(clip),
    maskCount: masks.length,
    maskHash: maskHash(clip),
    colorGradeHash: colorGradeHash(clip),
    textAnimHash: textAnimHash(clip),
  };
}
