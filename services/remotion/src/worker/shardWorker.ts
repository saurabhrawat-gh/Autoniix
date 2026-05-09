/**
 * Tier-shard worker (P0.11).
 *
 * Consumes `ShardJobData` from a tier queue (TIER0/TIER1/TIER2). The full
 * shard renderer (frame-range slice + tier-specific compositor) is a P1
 * deliverable — at P0 we ship the queue topology + a typed handler so the
 * surface is provable and the FlowProducer in `api/flow.ts` can be exercised
 * end-to-end against this code path.
 *
 * Behaviour today:
 *   - Validates the incoming payload.
 *   - Checks the diff cache (P0.3) and short-circuits with `cached: true` on hit.
 *   - On miss: throws a recognisable error so the orchestrator can route the
 *     work back to the legacy single-tier path until P1 lands.
 */

import { Worker, type Job } from "bullmq";
import { connection } from "../api/queue";
import {
  TIER0_QUEUE,
  TIER1_QUEUE,
  TIER2_QUEUE,
  type ShardJobData,
  type TierName,
} from "../api/queues";
import { lookupShard } from "../utils/diffCache";
import { logger } from "../utils/logger";
import { env } from "../utils/env";

const ROLE_TO_QUEUE: Record<"tier0" | "tier1" | "tier2", string> = {
  tier0: TIER0_QUEUE,
  tier1: TIER1_QUEUE,
  tier2: TIER2_QUEUE,
};

export class ShardRenderNotImplemented extends Error {
  constructor(public readonly tier: TierName) {
    super(`shard renderer for ${tier} is a P1 deliverable; falling back to legacy path`);
    this.name = "ShardRenderNotImplemented";
  }
}

export interface ShardJobResult {
  renderId: string;
  shardIndex: number;
  shardHash: string;
  tier: TierName;
  cached: boolean;
  s3Key?: string;
  size?: number;
  message?: string;
}

export async function handleShardJob(job: Job<ShardJobData>): Promise<ShardJobResult> {
  const data = job.data;
  if (!data || typeof data !== "object" || !data.renderId || typeof data.shardIndex !== "number") {
    throw new Error(`shard worker: malformed payload for job ${job.id}`);
  }

  // Diff-cache fast path.
  const cached = await lookupShard({
    shardHash: data.shardHash,
    tier: data.tier,
    codec: data.codec,
    width: data.width,
    height: data.height,
    fps: data.fps,
  });
  if (cached.hit) {
    logger.info(
      { renderId: data.renderId, shardIndex: data.shardIndex, s3Key: cached.s3Key, size: cached.size },
      "shard cache HIT",
    );
    return {
      renderId: data.renderId,
      shardIndex: data.shardIndex,
      shardHash: data.shardHash,
      tier: data.tier,
      cached: true,
      ...(cached.s3Key !== undefined ? { s3Key: cached.s3Key } : {}),
      ...(cached.size !== undefined ? { size: cached.size } : {}),
    };
  }

  // Miss → tier renderer not implemented yet at P0.
  throw new ShardRenderNotImplemented(data.tier);
}

export function startShardWorker(role: "tier0" | "tier1" | "tier2"): Worker<ShardJobData> {
  const queueName = ROLE_TO_QUEUE[role];
  const worker = new Worker<ShardJobData>(
    queueName,
    async (job) => handleShardJob(job),
    {
      connection,
      concurrency: env.RENDER_CONCURRENCY,
    },
  );

  worker.on("completed", (job, result: ShardJobResult) => {
    logger.info(
      {
        jobId: job.id,
        renderId: result.renderId,
        shardIndex: result.shardIndex,
        cached: result.cached,
      },
      "shard completed",
    );
  });
  worker.on("failed", (job, err) => {
    logger.error({ jobId: job?.id, err: err.message, name: err.name }, "shard failed");
  });

  logger.info({ role, queueName, concurrency: env.RENDER_CONCURRENCY }, "shard worker started");
  return worker;
}
