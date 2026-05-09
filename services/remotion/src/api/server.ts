import express from "express";
import pinoHttp from "pino-http";
import { nanoid } from "nanoid";
import { env } from "../utils/env";
import { logger } from "../utils/logger";
import { renderQueue, RENDER_QUEUE, type RenderJobData } from "./queue";
import { dispatchSharded } from "./flow";
import { lower } from "../scene-graph";
import { DirectionV3 } from "../schemas/directionV3";

const app = express();
app.use(express.json({ limit: "20mb" }));
app.use(pinoHttp({ logger }));

/** POST /api/render — enqueue a video render. */
app.post("/api/render", async (req, res) => {
  const body = req.body as Partial<RenderJobData> & { callbackUrl?: string };
  if (!body.composition || !body.inputProps) {
    return res.status(400).json({ error: "composition and inputProps are required" });
  }

  const renderId = `render_${nanoid(10)}`;

  // Sharded path (P0.2): SCENE_GRAPH_ENABLED + SHARDING_ENABLED + MainVideo composition
  // with inputProps containing a `direction` matching DirectionV3.
  if (
    env.SCENE_GRAPH_ENABLED &&
    env.SHARDING_ENABLED &&
    body.composition === "MainVideo" &&
    body.inputProps &&
    typeof body.inputProps === "object" &&
    "direction" in body.inputProps
  ) {
    const parsed = DirectionV3.safeParse((body.inputProps as { direction: unknown }).direction);
    if (parsed.success) {
      const graph = lower(parsed.data);
      const dispatch = await dispatchSharded({
        renderId,
        graph,
        codec: body.codec ?? "h264",
        outputFormat: (body.outputFormat as "mp4" | "webm") ?? "mp4",
        ...(body.callbackUrl ? { callbackUrl: body.callbackUrl } : {}),
        ...(body.exportStems ? { exportStems: true } : {}),
      });
      return res.json({
        renderId,
        status: "rendering",
        mode: "sharded",
        shardCount: dispatch.shardCount,
        shards: dispatch.shards,
        graphHash: graph.hash,
        estimatedDuration: 180,
      });
    }
    logger.warn({ renderId, issues: parsed.error.issues }, "scene-graph dispatch fallback: direction-v3 parse failed");
  }

  // Legacy single-queue path (default).
  const data: RenderJobData = {
    renderId,
    composition: body.composition,
    inputProps: body.inputProps,
    codec: body.codec ?? "h264",
    outputFormat: body.outputFormat ?? "mp4",
    quality: body.quality ?? 80,
    ...(body.width !== undefined ? { width: body.width } : {}),
    ...(body.height !== undefined ? { height: body.height } : {}),
    ...(body.callbackUrl ? { callbackUrl: body.callbackUrl } : {}),
    ...(body.exportStems ? { exportStems: true } : {}),
  };

  await renderQueue.add("render", data, {
    jobId: renderId,
    removeOnComplete: 100,
    removeOnFail: 100,
    attempts: 2,
    backoff: { type: "exponential", delay: 5_000 },
  });

  res.json({
    renderId,
    status: "rendering",
    mode: "legacy",
    estimatedDuration: 180,
  });
});

/** POST /api/thumbnail — same queue, ThumbnailComp composition. */
app.post("/api/thumbnail", async (req, res) => {
  const body = req.body as Partial<RenderJobData>;
  if (!body.inputProps) return res.status(400).json({ error: "inputProps required" });

  const renderId = `thumb_${nanoid(10)}`;
  const data: RenderJobData = {
    renderId,
    composition: "ThumbnailComp",
    inputProps: body.inputProps,
    codec: "h264",
    outputFormat: body.outputFormat ?? "png",
    quality: body.quality ?? 90,
    ...(body.width !== undefined ? { width: body.width } : { width: 1280 }),
    ...(body.height !== undefined ? { height: body.height } : { height: 720 }),
    ...(body.callbackUrl ? { callbackUrl: body.callbackUrl } : {}),
  };

  await renderQueue.add("thumbnail", data, { jobId: renderId });
  res.json({ renderId, status: "rendering" });
});

/** GET /api/render/:id — status + progress. */
app.get("/api/render/:id", async (req, res) => {
  const job = await renderQueue.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: "not found" });

  const state = await job.getState();
  const progress = typeof job.progress === "number" ? job.progress : 0;
  const result = job.returnvalue as
    | {
        outputUrl?: string;
        fileSize?: number;
        duration?: number;
        qc?: {
          pass: boolean;
          durationSec: number | null;
          meanLuminance: number | null;
          blackFraction: number | null;
          hasAudio: boolean;
        };
      }
    | undefined;

  const statusMap: Record<string, "rendering" | "done" | "failed"> = {
    completed: "done",
    failed: "failed",
    active: "rendering",
    waiting: "rendering",
    delayed: "rendering",
    paused: "rendering",
  };

  res.json({
    renderId: job.id,
    status: statusMap[state] ?? "rendering",
    progress,
    outputUrl: result?.outputUrl,
    fileSize: result?.fileSize,
    duration: result?.duration,
    qc: result?.qc,
    error: job.failedReason,
  });
});

/** GET /api/health */
app.get("/api/health", async (_req, res) => {
  const counts = await renderQueue.getJobCounts("active", "waiting", "delayed");
  const mem = process.memoryUsage();
  res.json({
    status: "healthy",
    queue: RENDER_QUEUE,
    activeRenders: counts.active,
    waiting: counts.waiting,
    maxConcurrent: env.RENDER_CONCURRENCY,
    memoryUsage: {
      rss: mem.rss,
      heapUsed: mem.heapUsed,
    },
  });
});

app.listen(env.API_PORT, () => {
  logger.info({ port: env.API_PORT }, "api listening");
});
