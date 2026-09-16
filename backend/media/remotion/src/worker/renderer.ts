import path from "node:path";
import fs from "node:fs";
import { renderMedia, renderStill, selectComposition, type Codec } from "@remotion/renderer";
import { env } from "../utils/env";
import { logger } from "../utils/logger";
import { uploadFile } from "../utils/storage";
import { DirectionV3 } from "../schemas/directionV3";
import { validateAgainstTemplate } from "../utils/compositionValidator";
import { normalizeLoudness } from "../utils/loudnessNormalizer";
import { stripAudio, extractMixedAudio } from "../utils/ffmpegStems";
import { postRenderQc } from "../utils/postRenderQc";
import { selectEncoder, type CodecFamily } from "../utils/encoder";
import { getOrBuildBundle } from "../utils/bundleCache";
import type { RenderJobData } from "../api/queue";

/** Bundle the Remotion entry, using the shared cache when available (P0.5). */
async function getBundle(): Promise<string> {
  const stats = await getOrBuildBundle();
  logger.info(
    { source: stats.source, hash: stats.hash.slice(0, 12), warmMs: stats.warmMs },
    "bundle ready",
  );
  return stats.bundlePath;
}

export interface RenderResult {
  outputUrl: string;
  fileSize: number;
  duration: number;
  /** Post-render QC metrics (always present for media renders). */
  qc?: {
    pass: boolean;
    durationSec: number | null;
    meanLuminance: number | null;
    blackFraction: number | null;
    hasAudio: boolean;
  };
  /** Present only when `exportStems: true` was requested. */
  stems?: {
    videoOnlyUrl: string;
    audioMixUrl: string;
  };
}

export class RenderQcError extends Error {
  constructor(public readonly reasons: string[]) {
    super(`post-render QC rejected output: ${reasons.join("; ")}`);
    this.name = "RenderQcError";
  }
}

export async function runRender(
  job: RenderJobData,
  onProgress: (p: number) => void,
): Promise<RenderResult> {
  const startedAt = Date.now();

  if (job.composition !== "ThumbnailComp") {
    const directionRaw = (job.inputProps as { direction?: unknown }).direction;
    if (directionRaw) {
      const parsed = DirectionV3.safeParse(directionRaw);
      if (!parsed.success) {
        throw new Error(`direction JSON failed schema validation: ${parsed.error.message}`);
      }
      const report = validateAgainstTemplate(parsed.data);
      if (report.warnings.length) {
        logger.warn({ warnings: report.warnings }, "template validation warnings");
      }
      if (!report.valid) {
        throw new Error(`template validation failed: ${report.errors.join("; ")}`);
      }
    }
  }

  const serveUrl = await getBundle();

  fs.mkdirSync(env.RENDER_TMP_DIR, { recursive: true });

  const composition = await selectComposition({
    serveUrl,
    id: job.composition,
    inputProps: job.inputProps,
  });

  if (job.composition === "ThumbnailComp") {
    const ext = job.outputFormat === "jpeg" ? "jpg" : "png";
    const outPath = path.join(env.RENDER_TMP_DIR, `${job.renderId}.${ext}`);
    await renderStill({
      composition: {
        ...composition,
        ...(job.width ? { width: job.width } : {}),
        ...(job.height ? { height: job.height } : {}),
      },
      serveUrl,
      output: outPath,
      inputProps: job.inputProps,
      imageFormat: ext === "jpg" ? "jpeg" : "png",
    });

    onProgress(1);
    const upload = await uploadFile(
      outPath,
      `thumbnails/${job.renderId}.${ext}`,
      ext === "jpg" ? "image/jpeg" : "image/png",
    );
    fs.unlinkSync(outPath);

    return {
      outputUrl: upload.url,
      fileSize: upload.size,
      duration: Math.round((Date.now() - startedAt) / 1000),
    };
  }

  const ext = job.outputFormat === "webm" ? "webm" : "mp4";
  const outPath = path.join(env.RENDER_TMP_DIR, `${job.renderId}.${ext}`);
  const codec: Codec = (job.codec ?? "h264") as Codec;

  const quality = job.quality ?? 80;
  const baseCrf = Math.max(1, Math.round(51 - (quality / 100) * 50));

  const codecFamily = (
    codec === "h264" || codec === "h265" || codec === "vp8" || codec === "vp9" ? codec : "h264"
  ) as CodecFamily;
  const enc = await selectEncoder(codecFamily);
  const crf = Math.max(1, Math.min(51, baseCrf + enc.crfOffset));
  logger.info(
    { encoder: enc.encoder, hwAccel: enc.hardwareAcceleration, baseCrf, crf },
    "encoder selected",
  );

  await renderMedia({
    composition,
    serveUrl,
    codec,
    outputLocation: outPath,
    inputProps: job.inputProps,
    concurrency: env.RENDER_CONCURRENCY,
    onProgress: ({ progress }) => onProgress(progress),
    imageFormat: "png",
    crf,
    jpegQuality: Math.max(80, quality),
    hardwareAcceleration: enc.hardwareAcceleration,
  });

  const targetLufs = (
    job.inputProps as { direction?: { audio?: { loudness_target_lufs?: number } } }
  ).direction?.audio?.loudness_target_lufs;
  if (typeof targetLufs === "number" && ext !== "webm") {
    try {
      logger.info({ targetLufs }, "normalizing loudness");
      await normalizeLoudness(outPath, { targetLufs });
    } catch (err) {
      logger.warn({ err }, "loudnorm failed — continuing with un-normalized audio");
    }
  }

  const directionForQc = (
    job.inputProps as {
      direction?: {
        meta?: { duration_target_seconds?: number };
        segments?: Array<{ duration_ms: number }>;
        audio?: { voiceover_url?: string };
      };
    }
  ).direction;
  const segMs = directionForQc?.segments?.reduce((a, s) => a + (s.duration_ms || 0), 0) ?? 0;
  const expectedDurationSec =
    segMs > 0 ? segMs / 1000 : (directionForQc?.meta?.duration_target_seconds ?? 0);
  const expectAudio = Boolean(directionForQc?.audio?.voiceover_url);
  const qcResult = await postRenderQc(outPath, {
    expectedDurationSec,
    expectAudio,
  });
  if (!qcResult.pass) {
    try {
      fs.unlinkSync(outPath);
    } catch {
      /* ignore */
    }
    throw new RenderQcError(qcResult.reasons);
  }

  const upload = await uploadFile(
    outPath,
    `renders/${job.renderId}.${ext}`,
    ext === "webm" ? "video/webm" : "video/mp4",
  );

  let stems: RenderResult["stems"] | undefined;
  if (job.exportStems && ext !== "webm") {
    try {
      const videoOnlyPath = path.join(env.RENDER_TMP_DIR, `${job.renderId}.video_only.${ext}`);
      const audioWavPath = path.join(env.RENDER_TMP_DIR, `${job.renderId}.audio.wav`);
      await Promise.all([
        stripAudio(outPath, videoOnlyPath),
        extractMixedAudio(outPath, audioWavPath),
      ]);
      const [videoUp, audioUp] = await Promise.all([
        uploadFile(
          videoOnlyPath,
          `renders/${job.renderId}.video_only.${ext}`,
          `video/${ext === "mp4" ? "mp4" : "webm"}`,
        ),
        uploadFile(audioWavPath, `renders/${job.renderId}.audio.wav`, "audio/wav"),
      ]);
      stems = { videoOnlyUrl: videoUp.url, audioMixUrl: audioUp.url };
      fs.unlinkSync(videoOnlyPath);
      fs.unlinkSync(audioWavPath);
    } catch (err) {
      logger.warn({ err }, "stems export failed — returning main MP4 only");
    }
  }

  fs.unlinkSync(outPath);

  return {
    outputUrl: upload.url,
    fileSize: upload.size,
    duration: Math.round((Date.now() - startedAt) / 1000),
    qc: {
      pass: qcResult.pass,
      durationSec: qcResult.metrics.durationSec,
      meanLuminance: qcResult.metrics.meanLuminance,
      blackFraction: qcResult.metrics.blackFraction,
      hasAudio: qcResult.metrics.hasAudio,
    },
    ...(stems ? { stems } : {}),
  };
}
