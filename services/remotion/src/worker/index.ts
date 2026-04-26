import { Worker } from "bullmq";
import { connection, RENDER_QUEUE, type RenderJobData } from "../api/queue";
import { env } from "../utils/env";
import { logger } from "../utils/logger";
import { runRender } from "./renderer";
import { dispatchCallback } from "../utils/callback";

const worker = new Worker<RenderJobData>(
  RENDER_QUEUE,
  async (job) => {
    const data = job.data;
    logger.info({ renderId: data.renderId, composition: data.composition }, "render start");

    try {
      const result = await runRender(data, (p) => {
        void job.updateProgress(p);
      });

      if (data.callbackUrl) {
        await dispatchCallback(data.callbackUrl, {
          renderId: data.renderId,
          status: "done",
          outputUrl: result.outputUrl,
          fileSize: result.fileSize,
          duration: result.duration,
        });
      }

      logger.info({ renderId: data.renderId, duration: result.duration }, "render done");
      return result;
    } catch (err) {
      logger.error({ err, renderId: data.renderId }, "render failed");
      if (data.callbackUrl) {
        await dispatchCallback(data.callbackUrl, {
          renderId: data.renderId,
          status: "failed",
          error: err instanceof Error ? err.message : String(err),
        });
      }
      throw err;
    }
  },
  {
    connection,
    concurrency: env.RENDER_CONCURRENCY,
  },
);

worker.on("completed", (job) => logger.info({ jobId: job.id }, "job completed"));
worker.on("failed", (job, err) => logger.error({ jobId: job?.id, err }, "job failed"));

logger.info({ concurrency: env.RENDER_CONCURRENCY }, "worker started");
