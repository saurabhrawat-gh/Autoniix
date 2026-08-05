/**
 * Tier-aware queue topology (P0.2 + P0.11).
 *
 * Backwards compatible: when `SHARDING_ENABLED=false` (default), only the
 * legacy `RENDER_QUEUE` is used. When sharding is on, jobs fan out to
 * tier-specific queues and a parent concat queue.
 *
 * See docs/future/remotion-vision/performance-and-scale.md §5.6.
 */

import { Queue, FlowProducer } from "bullmq";
import { connection, RENDER_QUEUE } from "./queue";

export const TIER0_QUEUE = "render-tier0";
export const TIER1_QUEUE = "render-tier1";
export const TIER2_QUEUE = "render-tier2";
export const CONCAT_QUEUE = "render-concat";
export const PREVIEW_QUEUE = "render-preview";

export type TierName = "t0" | "t1" | "t2";

export function tierToQueue(tier: TierName): string {
  switch (tier) {
    case "t0":
      return TIER0_QUEUE;
    case "t1":
      return TIER1_QUEUE;
    case "t2":
      return TIER2_QUEUE;
  }
}

/** Per-shard job payload. */
export interface ShardJobData {
  renderId: string;
  shardIndex: number;
  shardHash: string;
  tier: TierName;
  startMs: number;
  endMs: number;
  startFrame: number;
  endFrame: number;
  /** Inline scene-graph slice (full graph; renderer windows by frame). */
  sceneGraphJson: string;
  /** Codec/encoder selection (resolved by router). */
  codec: "h264" | "h265" | "vp8" | "vp9";
  outputFormat: "mp4" | "webm";
  width: number;
  height: number;
  fps: number;
}

/** Concat parent job payload. */
export interface ConcatJobData {
  renderId: string;
  graphHash: string;
  shardCount: number;
  /** Audio graph rendered once at parent. */
  audioGraphJson: string;
  /** Final encode params for the audio mux pass. */
  loudnessTargetLufs?: number;
  callbackUrl?: string;
  exportStems?: boolean;
}

export const tier0Queue = new Queue<ShardJobData>(TIER0_QUEUE, { connection });
export const tier1Queue = new Queue<ShardJobData>(TIER1_QUEUE, { connection });
export const tier2Queue = new Queue<ShardJobData>(TIER2_QUEUE, { connection });
export const concatQueue = new Queue<ConcatJobData>(CONCAT_QUEUE, { connection });

export const flowProducer = new FlowProducer({ connection });

export const QUEUES = {
  legacy: RENDER_QUEUE,
  t0: TIER0_QUEUE,
  t1: TIER1_QUEUE,
  t2: TIER2_QUEUE,
  concat: CONCAT_QUEUE,
  preview: PREVIEW_QUEUE,
} as const;
