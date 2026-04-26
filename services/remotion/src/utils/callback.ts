import { request } from "undici";
import { logger } from "./logger";

export interface CallbackPayload {
  renderId: string;
  status: "done" | "failed";
  outputUrl?: string;
  thumbnailUrl?: string;
  duration?: number;
  fileSize?: number;
  error?: string;
}

/**
 * POSTs the render result to the n8n (or other) webhook URL. Best-effort:
 * failures are logged but not thrown, since the render itself is already
 * persisted and retrievable via GET /api/render/:id.
 */
export async function dispatchCallback(url: string, payload: CallbackPayload): Promise<void> {
  try {
    const res = await request(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.statusCode >= 400) {
      logger.warn({ url, status: res.statusCode }, "callback returned non-2xx");
    } else {
      logger.info({ url, renderId: payload.renderId }, "callback dispatched");
    }
  } catch (err) {
    logger.error({ err, url }, "callback dispatch failed");
  }
}
