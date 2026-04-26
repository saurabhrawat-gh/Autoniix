import { Queue, QueueEvents } from "bullmq";
import IORedis from "ioredis";
import { env } from "../utils/env";

export const connection = new IORedis({
  host: env.REDIS_HOST,
  port: env.REDIS_PORT,
  password: env.REDIS_PASSWORD || undefined,
  maxRetriesPerRequest: null,
});

export const RENDER_QUEUE = "render-queue";

export interface RenderJobData {
  renderId: string;
  composition: "MainVideo" | "ShortFormVideo" | "ThumbnailComp";
  inputProps: Record<string, unknown>;
  codec: "h264" | "h265" | "vp8" | "vp9";
  outputFormat: "mp4" | "webm" | "png" | "jpeg";
  quality?: number;
  width?: number;
  height?: number;
  callbackUrl?: string;
  /**
   * When true, the worker also emits editor-friendly "stems" next to the main
   * MP4: a silent `video_only.mp4` + the mixed `audio.wav`. These let the user
   * import the render into Filmora/Premiere/DaVinci and independently replace
   * music, trim clips, or add new tracks.
   */
  exportStems?: boolean;
}

export const renderQueue = new Queue<RenderJobData>(RENDER_QUEUE, { connection });
export const renderQueueEvents = new QueueEvents(RENDER_QUEUE, { connection });
