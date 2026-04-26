import { spawn } from "node:child_process";
import { logger } from "./logger";

/**
 * Run ffmpeg with the given args and resolve/reject based on exit code. Captures
 * the last few KB of stderr for error messages.
 */
function runFfmpeg(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    logger.info({ args }, "ffmpeg stems op");
    const proc = spawn("ffmpeg", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    proc.stderr.on("data", (d: Buffer) => {
      stderr += d.toString();
      if (stderr.length > 8192) stderr = stderr.slice(-8192);
    });
    proc.on("error", reject);
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg failed (${code}): ${stderr.slice(-500)}`));
    });
  });
}

/**
 * Produces a silent (audio-stripped) copy of an existing MP4 suitable for
 * re-import into NLEs like Filmora / Premiere / DaVinci where the user wants
 * to add their own audio / soundtrack. Uses stream copy (no re-encode).
 */
export async function stripAudio(inputPath: string, outputPath: string): Promise<void> {
  await runFfmpeg(["-y", "-i", inputPath, "-c:v", "copy", "-an", outputPath]);
}

/**
 * Extract the mixed audio stream from an existing MP4 to a standalone WAV.
 * Useful when the downstream editor wants the Remotion-mixed audio as a stem.
 */
export async function extractMixedAudio(inputPath: string, outputWavPath: string): Promise<void> {
  await runFfmpeg(["-y", "-i", inputPath, "-vn", "-acodec", "pcm_s16le", "-ar", "48000", outputWavPath]);
}

/**
 * Concatenate multiple audio files with per-file start offsets (ms) into a
 * single WAV mix the same length as the full composition. Useful for building
 * an SFX stem that respects each cue's scheduled time.
 *
 * Implementation uses ffmpeg's `adelay` + `amix` filters.
 */
export async function mixDelayedAudio(
  inputs: Array<{ path: string; delayMs: number; volumeDb?: number }>,
  totalDurationSec: number,
  outputWavPath: string,
): Promise<void> {
  if (inputs.length === 0) {
    // Emit a silent WAV of the correct length so downstream pipelines have a stem file.
    await runFfmpeg([
      "-y",
      "-f",
      "lavfi",
      "-i",
      `anullsrc=r=48000:cl=stereo`,
      "-t",
      String(totalDurationSec),
      outputWavPath,
    ]);
    return;
  }

  const args: string[] = ["-y"];
  for (const inp of inputs) args.push("-i", inp.path);

  const filterParts = inputs.map((inp, i) => {
    const delay = Math.max(0, Math.round(inp.delayMs));
    const gain = typeof inp.volumeDb === "number" ? Math.pow(10, inp.volumeDb / 20) : 1;
    return `[${i}:a]adelay=${delay}|${delay},volume=${gain.toFixed(4)}[a${i}]`;
  });
  const mixInputs = inputs.map((_, i) => `[a${i}]`).join("");
  const filter =
    filterParts.join(";") +
    `;${mixInputs}amix=inputs=${inputs.length}:duration=longest:dropout_transition=0[aout]`;

  args.push(
    "-filter_complex",
    filter,
    "-map",
    "[aout]",
    "-t",
    String(totalDurationSec),
    "-acodec",
    "pcm_s16le",
    "-ar",
    "48000",
    outputWavPath,
  );

  await runFfmpeg(args);
}
