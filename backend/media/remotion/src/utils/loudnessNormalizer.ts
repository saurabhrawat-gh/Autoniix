import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { logger } from "./logger";

export interface LoudnessOptions {
  /** Target integrated loudness, e.g. -14 for YouTube. */
  targetLufs: number;
  /** Max true peak in dBFS, typically -1.0. */
  truePeakDbfs?: number;
  /** Loudness range. */
  lra?: number;
}

/**
 * Runs ffmpeg `loudnorm` one-pass normalization on a rendered file. Overwrites
 * the input path on success. Requires `ffmpeg` in PATH (bundled in Docker image).
 *
 * NOTE: one-pass loudnorm is sufficient for faceless-YT quality. Two-pass is
 * more accurate but doubles render time — defer to Phase 4 if needed.
 */
export async function normalizeLoudness(filePath: string, options: LoudnessOptions): Promise<void> {
  const { targetLufs, truePeakDbfs = -1.0, lra = 11 } = options;
  const dir = path.dirname(filePath);
  const ext = path.extname(filePath);
  const tmp = path.join(dir, `.norm-${Date.now()}${ext}`);

  await new Promise<void>((resolve, reject) => {
    const args = [
      "-y",
      "-i",
      filePath,
      "-af",
      `loudnorm=I=${targetLufs}:TP=${truePeakDbfs}:LRA=${lra}`,
      "-c:v",
      "copy",
      tmp,
    ];
    logger.info({ args }, "running ffmpeg loudnorm");
    const proc = spawn("ffmpeg", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    proc.stderr.on("data", (d: Buffer) => {
      stderr += d.toString();
    });
    proc.on("error", reject);
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg loudnorm failed (${code}): ${stderr.slice(-500)}`));
    });
  });

  await fs.rename(tmp, filePath);
}
