/**
 * FlowProducer dispatch — fans a single render request out into N tier-tagged
 * shard children + 1 concat parent.
 *
 * Activated by `SHARDING_ENABLED=true`. The legacy `renderQueue.add(...)` path
 * (api/server.ts) remains the default until the worker side of P0.2/P0.11 is
 * deployed.
 */

import type { SceneGraph } from "../scene-graph";
import { planShards, tagCapabilities } from "../scene-graph";
import {
  flowProducer,
  CONCAT_QUEUE,
  tierToQueue,
  type ShardJobData,
  type ConcatJobData,
  type TierName,
} from "./queues";
import { env } from "../utils/env";

export interface DispatchInput {
  renderId: string;
  graph: SceneGraph;
  codec?: ShardJobData["codec"];
  outputFormat?: ShardJobData["outputFormat"];
  callbackUrl?: string;
  exportStems?: boolean;
}

export interface DispatchResult {
  renderId: string;
  parentJobId: string;
  shardCount: number;
  shards: { index: number; tier: TierName; startMs: number; endMs: number; hash: string }[];
}

/**
 * Dispatch a SceneGraph render via FlowProducer. The parent (concat) job
 * runs only after all shard children succeed.
 */
export async function dispatchSharded(input: DispatchInput): Promise<DispatchResult> {
  const { renderId, graph } = input;
  const plan = planShards(graph, { targetShards: env.SHARDING_TARGET });

  const tagsByClipId = new Map(tagCapabilities(graph).map((t) => [t.clipId, t.tier]));

  const sceneGraphJson = JSON.stringify(graph);

  const shards = plan.shards.map((shard) => {
    let tier: TierName = "t2";
    for (const cid of shard.clipIds) {
      const t = tagsByClipId.get(cid) ?? "t1";
      tier = mergeTier(tier, t);
    }
    return { shard, tier };
  });

  const audioGraphJson = JSON.stringify(graph.audio);
  const concatData: ConcatJobData = {
    renderId,
    graphHash: graph.hash,
    shardCount: shards.length,
    audioGraphJson,
    loudnessTargetLufs: graph.audio.loudnessTargetLufs,
    callbackUrl: input.callbackUrl,
    exportStems: input.exportStems,
  };

  const flow = await flowProducer.add({
    name: "concat",
    queueName: CONCAT_QUEUE,
    data: concatData,
    opts: { jobId: renderId, removeOnComplete: 100, removeOnFail: 100 },
    children: shards.map(({ shard, tier }) => {
      const data: ShardJobData = {
        renderId,
        shardIndex: shard.index,
        shardHash: shard.hash,
        tier,
        startMs: shard.startMs,
        endMs: shard.endMs,
        startFrame: shard.startFrame,
        endFrame: shard.endFrame,
        sceneGraphJson,
        codec: input.codec ?? "h264",
        outputFormat: input.outputFormat ?? "mp4",
        width: graph.meta.resolution.width,
        height: graph.meta.resolution.height,
        fps: graph.meta.fps,
      };
      return {
        name: `shard-${shard.index}`,
        queueName: tierToQueue(tier),
        data,
        opts: {
          jobId: `${renderId}:s${shard.index}`,
          attempts: 2,
          backoff: { type: "exponential", delay: 5_000 },
          removeOnComplete: 100,
          removeOnFail: 100,
        },
      };
    }),
  });

  return {
    renderId,
    parentJobId: flow.job.id ?? renderId,
    shardCount: shards.length,
    shards: shards.map(({ shard, tier }) => ({
      index: shard.index,
      tier,
      startMs: shard.startMs,
      endMs: shard.endMs,
      hash: shard.hash,
    })),
  };
}

/** Tier merge: pick the more capability-demanding tier for the shard. */
function mergeTier(a: TierName, b: TierName): TierName {
  const order: Record<TierName, number> = { t2: 0, t0: 1, t1: 2 };
  return order[a] >= order[b] ? a : b;
}
