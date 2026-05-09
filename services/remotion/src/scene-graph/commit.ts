/**
 * Patch commit (P0.7).
 *
 * Applies a `Patch` to a `SceneGraph` and returns a new graph with hashes
 * recomputed. Pure function — does not mutate the input.
 *
 * Validation:
 *   - All `trackId` / `clipId` references must resolve.
 *   - `replaceClip` and `insertClip` must produce non-overlapping clip ranges
 *     within their target track.
 *   - On any violation, throws — orchestrator should catch + log + retry.
 */

import type {
  Clip,
  ClipFilterRef,
  ClipMaskRef,
  ColorGradeTrackRef,
  Compositing,
  Patch,
  PatchOp,
  SceneClip,
  SceneGraph,
  Track,
} from "./types";
import { hashNode } from "./hash";
import { validateCompositing } from "./compositing";
import {
  validateColorGradeTrack,
  type ColorGradeTrack,
} from "../registry/colorGrade";
import {
  validateFilters,
  type ClipFilter,
} from "../registry/clipFilters";

export function applyPatch(graph: SceneGraph, patch: Patch): SceneGraph {
  // Deep-clone via JSON (the IR is JSON-safe by construction).
  const next = JSON.parse(JSON.stringify(graph)) as SceneGraph;

  for (const op of patch.ops) {
    applyOp(next, op);
  }

  // Recompute clip hashes (cheap), track integrity, then root hash.
  for (const track of next.tracks) {
    assertNonOverlapping(track);
    for (const clip of track.clips) {
      clip.hash = hashNode(stripHash(clip));
    }
  }
  next.hash = "";
  next.hash = hashNode(next);
  return next;
}

function applyOp(graph: SceneGraph, op: PatchOp): void {
  switch (op.op) {
    case "replaceClip": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      t.clips[idx] = op.clip;
      return;
    }
    case "insertClip": {
      const t = mustTrack(graph, op.trackId);
      const idx = Math.max(0, Math.min(op.atIndex, t.clips.length));
      t.clips.splice(idx, 0, op.clip);
      return;
    }
    case "removeClip": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      t.clips.splice(idx, 1);
      return;
    }
    case "setTheme": {
      graph.theme = { ...graph.theme, ...op.theme };
      return;
    }
    case "setGradePreset": {
      graph.gradePreset = op.preset;
      return;
    }
    case "setAudio": {
      graph.audio = {
        ...graph.audio,
        ...op.audio,
        sfx: op.audio.sfx ?? graph.audio.sfx,
      };
      return;
    }
    case "setClipProps": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      const clip = t.clips[idx]!;
      if (clip.kind !== "scene") {
        throw new Error(`commit: setClipProps only supported on scene clips (got ${clip.kind})`);
      }
      const sceneClip = clip as SceneClip;
      sceneClip.sceneOverrides = { ...(sceneClip.sceneOverrides ?? {}), ...op.props };
      return;
    }
    case "setClipCompositing": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      const clip = t.clips[idx]!;
      if (clip.kind === "transition") {
        throw new Error(
          `commit: setClipCompositing not supported on transition clips (clip=${op.clipId})`,
        );
      }
      const compositing: Compositing = {
        ...((clip as { compositing?: Compositing }).compositing ?? {}),
        ...op.compositing,
      };
      validateCompositing(compositing, op.clipId);
      (clip as { compositing?: Compositing }).compositing = compositing;
      return;
    }
    case "setClipMasks": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      const clip = t.clips[idx]!;
      if (clip.kind === "transition") {
        throw new Error(
          `commit: setClipMasks not supported on transition clips (clip=${op.clipId})`,
        );
      }
      validateClipMasks(op.masks, op.clipId);
      (clip as { masks?: ClipMaskRef[] }).masks = op.masks;
      return;
    }
    case "setClipColorGrade": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      const clip = t.clips[idx]!;
      if (clip.kind !== "scene" && clip.kind !== "stock") {
        throw new Error(
          `commit: setClipColorGrade only supported on scene|stock clips (got ${clip.kind})`,
        );
      }
      // The IR-level structural type is loose; defer to the registry validator
      // which enforces the strict shape.
      validateColorGradeTrack(op.colorGradeTrack as unknown as ColorGradeTrack, op.clipId);
      (clip as { colorGradeTrack?: ColorGradeTrackRef }).colorGradeTrack =
        op.colorGradeTrack;
      return;
    }
    case "setClipFilters": {
      const t = mustTrack(graph, op.trackId);
      const idx = t.clips.findIndex((c) => c.id === op.clipId);
      if (idx < 0) throw new Error(`commit: clip ${op.clipId} not found on ${op.trackId}`);
      const clip = t.clips[idx]!;
      if (clip.kind !== "scene" && clip.kind !== "stock") {
        throw new Error(
          `commit: setClipFilters only supported on scene|stock clips (got ${clip.kind})`,
        );
      }
      validateFilters(op.filters as unknown as ClipFilter[], op.clipId);
      (clip as { filters?: ClipFilterRef[] }).filters = op.filters;
      return;
    }
  }
}

function validateClipMasks(masks: ClipMaskRef[], clipId: string): void {
  const ids = new Set<string>();
  for (const m of masks) {
    if (!m.id) throw new Error(`commit: mask on ${clipId} missing id`);
    if (ids.has(m.id)) throw new Error(`commit: duplicate mask id ${m.id} on ${clipId}`);
    ids.add(m.id);
    if (!m.track || !Array.isArray(m.track.keys) || m.track.keys.length === 0) {
      throw new Error(`commit: mask ${m.id} on ${clipId} has empty track`);
    }
    let prevT = -Infinity;
    for (const k of m.track.keys) {
      if (!Number.isFinite(k.tMs)) {
        throw new Error(`commit: mask ${m.id}/${clipId} non-finite tMs`);
      }
      if (k.tMs < prevT) {
        throw new Error(`commit: mask ${m.id}/${clipId} keys must be sorted by tMs`);
      }
      prevT = k.tMs;
    }
    if (m.blend && m.blend !== "intersect" && m.blend !== "add" && m.blend !== "subtract") {
      throw new Error(`commit: mask ${m.id}/${clipId} bad blend ${m.blend}`);
    }
  }
}

function mustTrack(graph: SceneGraph, trackId: string): Track {
  const t = graph.tracks.find((x) => x.id === trackId);
  if (!t) throw new Error(`commit: track ${trackId} not found`);
  return t;
}

type RangedClip = Exclude<Clip, { kind: "transition" }>;

function isRangedClip(c: Clip): c is RangedClip {
  return c.kind !== "transition";
}

function assertNonOverlapping(track: Track): void {
  const ranged = track.clips.filter(isRangedClip);
  const sorted = [...ranged].sort((a, b) => a.range[0] - b.range[0]);
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1]!;
    const cur = sorted[i]!;
    if (cur.range[0] < prev.range[1]) {
      throw new Error(
        `commit: overlapping clips ${prev.id} (end=${prev.range[1]}) and ${cur.id} (start=${cur.range[0]})`,
      );
    }
  }
}

function stripHash<T extends Clip>(c: T): Omit<T, "hash"> {
  const { hash: _hash, ...rest } = c;
  return rest as Omit<T, "hash">;
}
