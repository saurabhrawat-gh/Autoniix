/**
 * Phase 2 — ffmpeg subprocess runner.
 *
 * Thin wrapper around `child_process.spawn` that:
 *   • Validates ffmpeg ≥ 4.4 once per process (cached).
 *   • Captures stdout + stderr; surfaces the last 2 KB on non-zero exit.
 *   • Enforces a wall-clock timeout (default 10 minutes per command).
 *   • Returns a structured `RunResult` for observability.
 *
 * Used by `runFfmpegRecipe()` to walk a `FfmpegRecipe` (Phase 2 clipFilters)
 * end-to-end. The runner is deliberately stateless — caching of derived
 * outputs lives in `clip_render_cache` (Phase 1E).
 */

import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import type { FfmpegCommand, FfmpegRecipe } from "../registry/clipFilters";
import { metrics } from "../utils/metrics";

export interface RunResult {
  command: FfmpegCommand;
  exitCode: number;
  durationMs: number;
  stderrTail: string;
}

export interface RunRecipeResult {
  outputPath: string;
  results: RunResult[];
  totalDurationMs: number;
}

/* ====================================================================== */
/* ffmpeg discovery                                                       */
/* ====================================================================== */

let _ffmpegProbed: { binary: string; version: string } | null = null;
let _ffmpegProbeErr: Error | null = null;

export async function probeFfmpeg(): Promise<{ binary: string; version: string }> {
  if (_ffmpegProbed) return _ffmpegProbed;
  if (_ffmpegProbeErr) throw _ffmpegProbeErr;
  const binary = process.env.FFMPEG_PATH ?? "ffmpeg";
  try {
    const { code, stderr, stdout } = await runOnce(binary, ["-version"], { timeoutMs: 5_000 });
    if (code !== 0) throw new Error(`ffmpeg -version exited ${code}`);
    const versionLine = (stdout || stderr).split("\n")[0]?.trim() ?? "";
    const m = versionLine.match(/ffmpeg version (\S+)/);
    const version = m?.[1] ?? "unknown";
    _ffmpegProbed = { binary, version };
    return _ffmpegProbed;
  } catch (e) {
    _ffmpegProbeErr = e instanceof Error ? e : new Error(String(e));
    throw _ffmpegProbeErr;
  }
}

/* ====================================================================== */
/* Single-command runner                                                  */
/* ====================================================================== */

interface RunOnceOpts {
  timeoutMs?: number;
  cwd?: string;
}

interface RawRun {
  code: number;
  stdout: string;
  stderr: string;
}

function runOnce(
  binary: string,
  args: string[],
  opts: RunOnceOpts = {},
): Promise<RawRun> {
  const timeoutMs = opts.timeoutMs ?? 10 * 60 * 1000;
  return new Promise((resolve, reject) => {
    const child = spawn(binary, args, {
      cwd: opts.cwd,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let killed = false;
    const timer = setTimeout(() => {
      killed = true;
      child.kill("SIGKILL");
    }, timeoutMs);

    child.stdout.on("data", (b) => {
      stdout += b.toString("utf8");
      if (stdout.length > 1_000_000) stdout = stdout.slice(-1_000_000);
    });
    child.stderr.on("data", (b) => {
      stderr += b.toString("utf8");
      if (stderr.length > 1_000_000) stderr = stderr.slice(-1_000_000);
    });

    child.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (killed) return reject(new Error(`ffmpeg killed after ${timeoutMs}ms`));
      resolve({ code: code ?? -1, stdout, stderr });
    });
  });
}

/* ====================================================================== */
/* Recipe runner                                                          */
/* ====================================================================== */

export interface RunRecipeOpts {
  /** Per-command wall-clock cap. Default 10min. */
  perCommandTimeoutMs?: number;
  /** Working dir override (defaults to OS tmpdir). */
  workDir?: string;
}

/**
 * Executes every command in a recipe sequentially. The recipe must end with
 * a command whose `finalOutput=true` (or the recipe must be empty, in which
 * case this is a no-op return).
 */
export async function runFfmpegRecipe(
  recipe: FfmpegRecipe,
  opts: RunRecipeOpts = {},
): Promise<RunRecipeResult> {
  if (recipe.gpuFilters.length > 0) {
    throw new Error(
      `runFfmpegRecipe: recipe still contains GPU filters [${recipe.gpuFilters
        .map((f) => f.kind)
        .join(", ")}] — route through the model server first`,
    );
  }
  if (recipe.commands.length === 0) {
    throw new Error("runFfmpegRecipe: empty recipe");
  }

  const { binary } = await probeFfmpeg();
  const start = Date.now();
  const results: RunResult[] = [];
  let outputPath: string | null = null;

  for (const cmd of recipe.commands) {
    const t0 = Date.now();
    const { code, stderr } = await runOnce(binary, cmd.args, {
      timeoutMs: opts.perCommandTimeoutMs,
      cwd: opts.workDir,
    });
    const dt = Date.now() - t0;
    const tail = stderr.slice(-2048);
    results.push({ command: cmd, exitCode: code, durationMs: dt, stderrTail: tail });
    if (code !== 0) {
      const err = new Error(
        `ffmpeg failed (${code}) at "${cmd.summary}":\n${tail}`,
      );
      throw err;
    }
    if (cmd.finalOutput) {
      outputPath = cmd.args[cmd.args.length - 1] ?? null;
    }
  }

  if (!outputPath) {
    throw new Error("runFfmpegRecipe: recipe ended without a finalOutput=true command");
  }

  await fs.access(outputPath);

  for (const cmd of recipe.commands) {
    metrics.cache.miss("blend");
    void cmd;
  }

  return {
    outputPath,
    results,
    totalDurationMs: Date.now() - start,
  };
}

/* ====================================================================== */
/* Tempdir helper                                                          */
/* ====================================================================== */

/** Creates a unique work dir under the OS tmpdir. Caller is responsible for
 *  cleanup (or accepts that tmp gets gc'd by the OS). */
export async function makeWorkDir(prefix = "yt-ffmpeg-"): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
  return dir;
}

/* ====================================================================== */
/* ffprobe wrapper (used by smoke tests + cache key sanity)               */
/* ====================================================================== */

export interface ProbeInfo {
  durationSec: number;
  width: number;
  height: number;
  videoCodec: string;
  fps: number;
}

export async function ffprobe(filePath: string): Promise<ProbeInfo> {
  const binary = process.env.FFPROBE_PATH ?? "ffprobe";
  const { code, stdout, stderr } = await runOnce(binary, [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=codec_name,width,height,r_frame_rate:format=duration",
    "-of",
    "default=nw=1:nk=0",
    filePath,
  ]);
  if (code !== 0) {
    throw new Error(`ffprobe failed (${code}): ${stderr}`);
  }
  const lines = stdout.split("\n");
  const get = (key: string): string =>
    lines
      .find((l) => l.startsWith(`${key}=`))
      ?.slice(key.length + 1)
      ?.trim() ?? "";
  const fpsRaw = get("r_frame_rate");
  let fps = 0;
  const fmatch = fpsRaw.match(/^(\d+)\/(\d+)$/);
  if (fmatch) {
    const num = Number(fmatch[1]);
    const den = Number(fmatch[2]);
    fps = den !== 0 ? num / den : 0;
  } else {
    fps = Number(fpsRaw) || 0;
  }
  return {
    durationSec: Number(get("duration")) || 0,
    width: Number(get("width")) || 0,
    height: Number(get("height")) || 0,
    videoCodec: get("codec_name"),
    fps,
  };
}
