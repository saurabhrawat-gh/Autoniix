/**
 * Sharder — splits a SceneGraph timeline into N frame-range shards whose
 * boundaries align to scene-clip boundaries (never mid-scene).
 *
 * See docs/future/remotion-vision/02-FUTURE-ENGINE-ARCHITECTURE.md §2.6.
 *
 * Invariants:
 *   - Shards are contiguous and cover [0, durationMs) exactly.
 *   - Each shard boundary falls on a scene-clip boundary on the "video" track.
 *   - Audio is rendered at the parent (concat) job, never per-shard.
 *   - Shards are independently encodable: keyframes forced at boundaries via
 *     `forceKeyFrameAtMs` (consumed by the worker when it invokes ffmpeg).
 */

import type { Clip, SceneGraph, SceneClip } from "./types";
import { hashNode } from "./hash";

export type Shard = {
  index: number;
  startMs: number;
  endMs: number;
  startFrame: number;
  endFrame: number;
  clipIds: string[];
  /** Stable hash for diff-cache lookup (P0.3). */
  hash: string;
};

export type ShardPlan = {
  graphHash: string;
  fps: number;
  totalFrames: number;
  shards: Shard[];
  /** Cut points on the master video track; first is 0, last is durationMs. */
  cutPointsMs: number[];
};

export type ShardOptions = {
  /** Target number of shards. The actual count may be smaller if there are
   *  fewer scene boundaries available (we never split mid-scene). */
  targetShards?: number;
  /** Hard floor on shard duration. Prevents tiny scenes producing many micro-shards. */
  minShardMs?: number;
};

const DEFAULT_OPTIONS: Required<ShardOptions> = {
  targetShards: 4,
  minShardMs: 2000,
};

export function planShards(graph: SceneGraph, opts: ShardOptions = {}): ShardPlan {
  const cfg = { ...DEFAULT_OPTIONS, ...opts };

  const videoTrack = graph.tracks.find((t) => t.kind === "video");
  if (!videoTrack || videoTrack.clips.length === 0) {
    throw new Error("sharder: SceneGraph has no video track or no clips");
  }
  const sceneClips = videoTrack.clips.filter((c) => c.kind === "scene") as SceneClip[];
  if (sceneClips.length === 0) {
    throw new Error("sharder: video track has no scene clips");
  }

  const allBoundaries = sceneClips.map((c) => c.range[0]);
  allBoundaries.push(sceneClips[sceneClips.length - 1]!.range[1]);
  const totalDurationMs = graph.meta.durationMs;
  const idealShardMs = Math.max(cfg.minShardMs, Math.floor(totalDurationMs / cfg.targetShards));

  const cutPointsMs: number[] = [allBoundaries[0]!];
  let lastCut = allBoundaries[0]!;
  for (let i = 1; i < allBoundaries.length - 1; i++) {
    const candidate = allBoundaries[i]!;
    if (candidate - lastCut >= idealShardMs) {
      cutPointsMs.push(candidate);
      lastCut = candidate;
    }
  }
  cutPointsMs.push(allBoundaries[allBoundaries.length - 1]!);

  const fps = graph.meta.fps;
  const shards: Shard[] = [];
  for (let i = 0; i < cutPointsMs.length - 1; i++) {
    const startMs = cutPointsMs[i]!;
    const endMs = cutPointsMs[i + 1]!;
    const containedClips = sceneClips.filter(
      (c) => c.range[0] >= startMs && c.range[1] <= endMs,
    );
    const shard: Shard = {
      index: i,
      startMs,
      endMs,
      startFrame: msToFrames(startMs, fps),
      endFrame: msToFrames(endMs, fps),
      clipIds: containedClips.map((c) => c.id),
      hash: hashShard(graph, startMs, endMs, containedClips),
    };
    shards.push(shard);
  }

  return {
    graphHash: graph.hash,
    fps,
    totalFrames: msToFrames(totalDurationMs, fps),
    shards,
    cutPointsMs,
  };
}

export function msToFrames(ms: number, fps: number): number {
  return Math.round((ms / 1000) * fps);
}

/**
 * Shard hash = hash over the slice of clips it contains + the timeline
 * window. The audio graph is INTENTIONALLY excluded because audio is mixed
 * once at the parent.
 */
function hashShard(graph: SceneGraph, startMs: number, endMs: number, clips: Clip[]): string {
  return hashNode({
    graphMeta: {
      videoId: graph.meta.videoId,
      fps: graph.meta.fps,
      resolution: graph.meta.resolution,
    },
    theme: graph.theme,
    gradePreset: graph.gradePreset,
    globalEffects: graph.globalEffects,
    globalOverlays: graph.globalOverlays,
    branding: graph.branding,
    window: { startMs, endMs },
    clips,
  });
}
