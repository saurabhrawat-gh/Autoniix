/**
 * Concat parent worker (P0.11).
 *
 * Consumes `ConcatJobData` from CONCAT_QUEUE. Runs after all shard children
 * succeed (FlowProducer parent semantics). At P0 it ships as a typed stub —
 * the real ffmpeg `concat` + audio mux pass lands in P1 alongside the tier
 * shard renderers.
 */

import { Worker, type Job } from "bullmq";
import { connection } from "../api/queue";
import { CONCAT_QUEUE, type ConcatJobData } from "../api/queues";
import { logger } from "../utils/logger";
import { env } from "../utils/env";

export interface ConcatJobResult {
  renderId: string;
  graphHash: string;
  shardCount: number;
  status: "unimplemented";
  message: string;
}

export async function handleConcatJob(job: Job<ConcatJobData>): Promise<ConcatJobResult> {
  const data = job.data;
  if (!data || !data.renderId || !data.graphHash) {
    throw new Error(`concat worker: malformed payload for job ${job.id}`);
  }
  logger.info(
    { renderId: data.renderId, graphHash: data.graphHash, shardCount: data.shardCount },
    "concat job received (P0 stub)",
  );
  return {
    renderId: data.renderId,
    graphHash: data.graphHash,
    shardCount: data.shardCount,
    status: "unimplemented",
    message: "concat parent is a P1 deliverable; shard renderer must land first",
  };
}

export function startConcatWorker(): Worker<ConcatJobData> {
  const worker = new Worker<ConcatJobData>(
    CONCAT_QUEUE,
    async (job) => handleConcatJob(job),
    {
      connection,
      // Concat is cheap; allow more parallelism than shard workers.
      concurrency: Math.max(env.RENDER_CONCURRENCY, 2),
    },
  );
  worker.on("failed", (job, err) => logger.error({ jobId: job?.id, err: err.message }, "concat failed"));
  logger.info({ queueName: CONCAT_QUEUE }, "concat worker started");
  return worker;
}
