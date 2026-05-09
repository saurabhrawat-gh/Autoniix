import { spawn } from "node:child_process";
import { statSync } from "node:fs";
import { logger } from "./logger";

export interface PostRenderQcOptions {
  /** Expected total duration in seconds (sum of segment durations). */
  expectedDurationSec: number;
  /** Composition expected to contain narration audio. */
  expectAudio: boolean;
  /** Min average pixel value (0–255) below which the render is rejected. */
  minMeanLuminance?: number;
  /** Allow ± seconds vs expectedDurationSec. */
  durationToleranceSec?: number;
  /** Min file size in bytes — anything smaller is suspicious. */
  minFileSizeBytes?: number;
}

export interface PostRenderQcResult {
  pass: boolean;
  reasons: string[];
  metrics: {
    fileSizeBytes: number;
    durationSec: number | null;
    hasVideo: boolean;
    hasAudio: boolean;
    meanLuminance: number | null;
    blackFraction: number | null;
  };
}

interface FfprobeStream {
  codec_type?: string;
  codec_name?: string;
  duration?: string;
}
interface FfprobeOutput {
  streams?: FfprobeStream[];
  format?: { duration?: string; size?: string };
}

function runCmd(cmd: string, args: string[], opts: { timeoutMs?: number } = {}): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const proc = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let killed = false;
    const timer = opts.timeoutMs
      ? setTimeout(() => {
          killed = true;
          proc.kill("SIGKILL");
        }, opts.timeoutMs)
      : null;
    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); if (stderr.length > 32 * 1024) stderr = stderr.slice(-32 * 1024); });
    proc.on("error", () => { if (timer) clearTimeout(timer); resolve({ code: -1, stdout, stderr }); });
    proc.on("close", (code) => { if (timer) clearTimeout(timer); resolve({ code: killed ? -1 : (code ?? -1), stdout, stderr }); });
  });
}

async function ffprobe(path: string): Promise<FfprobeOutput | null> {
  const { code, stdout } = await runCmd(
    "ffprobe",
    ["-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
    { timeoutMs: 15_000 },
  );
  if (code !== 0) return null;
  try {
    return JSON.parse(stdout) as FfprobeOutput;
  } catch {
    return null;
  }
}

/**
 * Compute a robust average luminance via ffmpeg's `signalstats` filter sampled
 * over a handful of frames. Returns mean Y in 0–255, or null on failure.
 */
async function meanLuminance(path: string, sampleFrames = 20): Promise<number | null> {
  // signalstats writes YAVG metadata per frame; metadata=print emits to stderr.
  const args = [
    "-hide_banner",
    "-nostats",
    "-i", path,
    "-vf", `select='not(mod(n\\,${Math.max(1, Math.floor(sampleFrames))}))',signalstats,metadata=print:key=lavfi.signalstats.YAVG`,
    "-an",
    "-f", "null",
    "-",
  ];
  const { code, stderr } = await runCmd("ffmpeg", args, { timeoutMs: 30_000 });
  if (code !== 0 && !stderr) return null;
  const matches = stderr.matchAll(/YAVG=([0-9.]+)/g);
  const values: number[] = [];
  for (const m of matches) {
    const v = Number(m[1]);
    if (!Number.isNaN(v)) values.push(v);
  }
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/**
 * Use ffmpeg's `blackdetect` filter to compute fraction of duration that is
 * detected as black (mean luminance below threshold). Returns 0–1 or null.
 */
async function blackDetect(path: string, totalDurationSec: number): Promise<number | null> {
  const args = [
    "-hide_banner",
    "-nostats",
    "-i", path,
    "-vf", "blackdetect=d=0.2:pix_th=0.10",
    "-an",
    "-f", "null",
    "-",
  ];
  const { stderr } = await runCmd("ffmpeg", args, { timeoutMs: 30_000 });
  const matches = [...stderr.matchAll(/black_start:([0-9.]+).*?black_end:([0-9.]+)/g)];
  if (matches.length === 0) return 0;
  let totalBlack = 0;
  for (const m of matches) {
    const start = Number(m[1]);
    const end = Number(m[2]);
    if (!Number.isNaN(start) && !Number.isNaN(end) && end > start) {
      totalBlack += end - start;
    }
  }
  if (totalDurationSec <= 0) return null;
  return Math.min(1, totalBlack / totalDurationSec);
}

/**
 * Run end-to-end QC on a freshly rendered MP4. The verdict is conservative:
 * if any signal is suspicious (black-frame fraction > 25%, mean luminance
 * < threshold, missing streams, file < 50 KB, duration off by > tolerance),
 * we reject. Caller should NOT upload a rejected render.
 */
export async function postRenderQc(
  path: string,
  opts: PostRenderQcOptions,
): Promise<PostRenderQcResult> {
  const reasons: string[] = [];
  const minLum = opts.minMeanLuminance ?? 12; // 0–255
  const tol = opts.durationToleranceSec ?? Math.max(0.5, opts.expectedDurationSec * 0.1);
  const minSize = opts.minFileSizeBytes ?? 50_000;

  let fileSize = 0;
  try {
    fileSize = statSync(path).size;
  } catch {
    return {
      pass: false,
      reasons: ["render output file not found"],
      metrics: { fileSizeBytes: 0, durationSec: null, hasVideo: false, hasAudio: false, meanLuminance: null, blackFraction: null },
    };
  }
  if (fileSize < minSize) reasons.push(`file too small (${fileSize}B < ${minSize}B)`);

  const probe = await ffprobe(path);
  const streams = probe?.streams ?? [];
  const hasVideo = streams.some((s) => s.codec_type === "video");
  const hasAudio = streams.some((s) => s.codec_type === "audio");
  const durationSec = probe?.format?.duration ? Number(probe.format.duration) : null;

  if (!hasVideo) reasons.push("no video stream");
  if (opts.expectAudio && !hasAudio) reasons.push("expected audio stream missing");
  if (durationSec === null) reasons.push("could not read duration");
  else if (Math.abs(durationSec - opts.expectedDurationSec) > tol) {
    reasons.push(
      `duration mismatch: got ${durationSec.toFixed(2)}s, expected ${opts.expectedDurationSec.toFixed(2)}s (±${tol.toFixed(2)})`,
    );
  }

  let meanLum: number | null = null;
  let blackFrac: number | null = null;
  if (hasVideo) {
    [meanLum, blackFrac] = await Promise.all([
      meanLuminance(path),
      blackDetect(path, durationSec ?? opts.expectedDurationSec),
    ]);
    if (meanLum !== null && meanLum < minLum) {
      reasons.push(`mean luminance ${meanLum.toFixed(1)} < ${minLum} (likely black-frame render)`);
    }
    if (blackFrac !== null && blackFrac > 0.25) {
      reasons.push(`black-frame fraction ${(blackFrac * 100).toFixed(1)}% > 25%`);
    }
  }

  const pass = reasons.length === 0;
  const result: PostRenderQcResult = {
    pass,
    reasons,
    metrics: {
      fileSizeBytes: fileSize,
      durationSec,
      hasVideo,
      hasAudio,
      meanLuminance: meanLum,
      blackFraction: blackFrac,
    },
  };
  logger.info({ qc: result }, pass ? "post-render qc pass" : "post-render qc reject");
  return result;
}
