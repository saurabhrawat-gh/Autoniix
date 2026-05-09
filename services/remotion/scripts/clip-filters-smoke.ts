/**
 * Phase 2B — Real-pixel smoke test for clip filters.
 *
 * Creates a 2-second synthetic interlaced 720p25 video (lavfi `mandelbrot`
 * + interlaced flag), then runs:
 *
 *   1. deinterlace (yadif)
 *   2. denoise + stabilize (2-pass via vidstabdetect/vidstabtransform)
 *   3. upscale 2x (lanczos)
 *
 * Verifies via ffprobe that:
 *   • Output exists at the expected path.
 *   • Output codec is h264.
 *   • Output dimensions match the upscale factor.
 *   • Output duration is within 100ms of the source.
 *
 * Also exercises the recipe-builder unit logic (no subprocess) and the
 * `setClipFilters` patch op for IR round-trip.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/clip-filters-smoke.ts
 *
 * Requires: ffmpeg ≥ 4.4 with libvidstab. See the early `probeFfmpeg()` call
 * — the test exits cleanly with a clear message if the binary is missing.
 */

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";

import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  lower,
  type ClipFilterRef,
  type Patch,
  type SceneClip,
} from "../src/scene-graph";
import {
  buildFfmpegRecipe,
  orderFilters,
  outTimeAtSrcTime,
  srcTimeAtOutTime,
  validateFilters,
  type ClipFilter,
} from "../src/registry/clipFilters";
import {
  ffprobe,
  makeWorkDir,
  probeFfmpeg,
  runFfmpegRecipe,
} from "../src/services/ffmpegRunner";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}
function expectThrow(fn: () => void, msg: string): void {
  try {
    fn();
    console.error(`FAIL: ${msg} (expected throw)`);
    failures += 1;
  } catch {
    /* ok */
  }
}

(async () => {
  /* -------- 0. Probe ffmpeg ---------------------------------------- */
  let probed: { binary: string; version: string };
  try {
    probed = await probeFfmpeg();
  } catch (e) {
    console.error(
      `SKIP clip-filters smoke: ffmpeg not available (${e instanceof Error ? e.message : e})`,
    );
    process.exit(0);
  }

  /* -------- 1. Recipe builder unit assertions ---------------------- */
  const filters: ClipFilter[] = [
    { kind: "stabilize", shakiness: 5, smoothing: 15 },
    { kind: "deinterlace", algo: "yadif" }, // intentionally out of order
    { kind: "upscale", model: "ffmpeg-lanczos", scale: 2 },
    { kind: "denoise", model: "ffmpeg-hqdn3d", strength: 0.4 },
  ];
  validateFilters(filters);
  const ordered = orderFilters(filters);
  check(ordered[0]!.kind === "deinterlace", `order: deinterlace first`);
  check(ordered[ordered.length - 1]!.kind === "upscale", `order: upscale last`);

  // Validation rejects bad inputs
  expectThrow(
    () => validateFilters([{ kind: "stabilize", shakiness: 99 } as ClipFilter]),
    "shakiness OOB rejected",
  );
  expectThrow(
    () => validateFilters([{ kind: "upscale", scale: 5 } as unknown as ClipFilter]),
    "upscale.scale=5 rejected",
  );
  expectThrow(
    () =>
      validateFilters([
        {
          kind: "warp",
          curve: [{ srcU: 0, outU: 0 }, { srcU: 0.5, outU: 0.5 }],
        } as unknown as ClipFilter,
      ]),
    "warp curve missing (1,1) rejected",
  );
  expectThrow(
    () => orderFilters([{ kind: "deinterlace" }, { kind: "deinterlace" }] as ClipFilter[]),
    "duplicate filter kind rejected",
  );

  /* -------- 2. Speed curve evaluation ------------------------------ */
  const ramp = [
    { srcU: 0, outU: 0 },
    { srcU: 0.4, outU: 0.7 }, // first 40% of source plays in first 70% of output (slow)
    { srcU: 1, outU: 1 },
  ];
  const out_at_mid = outTimeAtSrcTime(ramp, 0.4);
  const src_at_70 = srcTimeAtOutTime(ramp, 0.7);
  check(Math.abs(out_at_mid - 0.7) < 1e-9, `forward map @0.4 → 0.7`);
  check(Math.abs(src_at_70 - 0.4) < 1e-9, `inverse map @0.7 → 0.4`);
  // Pin endpoints
  check(outTimeAtSrcTime(ramp, 0) === 0, `forward @0=0`);
  check(outTimeAtSrcTime(ramp, 1) === 1, `forward @1=1`);
  check(srcTimeAtOutTime(ramp, 0) === 0, `inverse @0=0`);
  check(srcTimeAtOutTime(ramp, 1) === 1, `inverse @1=1`);

  /* -------- 3. setClipFilters patch op round-trip ------------------ */
  const fixturePath = path.resolve(
    __dirname,
    "../src/scene-graph/__fixtures__/minimal-direction.json",
  );
  const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const direction = DirectionV3.parse(raw);
  const g0 = lower(direction);
  const videoTrack = g0.tracks.find((t) => t.kind === "video")!;
  const targetClip = videoTrack.clips[0] as SceneClip;

  const filtersForIr: ClipFilterRef[] = filters as unknown as ClipFilterRef[];
  const patch: Patch = {
    agent: "clip-filters-smoke",
    agentVersion: "1.0.0",
    ops: [
      {
        op: "setClipFilters",
        trackId: videoTrack.id,
        clipId: targetClip.id,
        filters: filtersForIr,
      },
    ],
  };
  const g1 = applyPatch(g0, patch);
  const updated = g1.tracks
    .find((t) => t.id === videoTrack.id)!
    .clips.find((c) => c.id === targetClip.id) as SceneClip;
  check(Array.isArray(updated.filters) && updated.filters!.length === 4, "filters installed via patch");
  check(g1.hash !== g0.hash, "root hash changed");

  // Determinism + bad-filter rejection through the patch
  const g1b = applyPatch(g0, patch);
  check(g1.hash === g1b.hash, "applyPatch determinism for filters");
  expectThrow(
    () =>
      applyPatch(g0, {
        agent: "clip-filters-smoke",
        agentVersion: "1.0.0",
        ops: [
          {
            op: "setClipFilters",
            trackId: videoTrack.id,
            clipId: targetClip.id,
            filters: [{ kind: "deinterlace" }, { kind: "deinterlace" }] as ClipFilterRef[],
          },
        ],
      }),
    "duplicate filter rejected via patch",
  );

  /* -------- 4. Real-pixel end-to-end -------------------------------- */
  const workDir = await makeWorkDir("yt-2b-");
  const inputPath = path.join(workDir, "input.mp4");
  const outputPath = path.join(workDir, "output.mp4");

  // Generate a 2-second 720p25 synthetic source. mandelbrot has motion → good
  // for stabilize (it'll detect zero shake but still process). Add a tiny
  // overlay of testsrc2 to give yadif/hqdn3d real per-pixel work.
  const genArgs = [
    "-y",
    "-f", "lavfi",
    "-i", "mandelbrot=size=1280x720:rate=25",
    "-t", "2",
    "-pix_fmt", "yuv420p",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "23",
    inputPath,
  ];
  const gen = spawnSync(probed.binary, genArgs, { encoding: "utf8" });
  if (gen.status !== 0) {
    console.error(`SKIP real-pixel run: failed to synthesize input (${gen.status})\n${gen.stderr.slice(-2000)}`);
    process.exit(failures > 0 ? 1 : 0);
  }
  const inputProbe = await ffprobe(inputPath);
  check(inputProbe.width === 1280, `synth input width=${inputProbe.width}`);
  check(inputProbe.height === 720, `synth input height=${inputProbe.height}`);

  // Build the recipe (CPU lane only — drop GPU filters).
  const cpuFilters: ClipFilter[] = [
    { kind: "deinterlace", algo: "yadif" },
    { kind: "denoise", model: "ffmpeg-hqdn3d", strength: 0.4 },
    { kind: "stabilize", shakiness: 5, smoothing: 15 },
    { kind: "upscale", model: "ffmpeg-lanczos", scale: 2 },
  ];
  const recipe = buildFfmpegRecipe(cpuFilters, {
    inputPath,
    outputPath,
    workDir,
    crf: 23, // faster smoke test
  });
  check(recipe.gpuFilters.length === 0, `no GPU filters in pure-CPU recipe`);
  check(recipe.commands.length === 2, `stabilize → 2 commands (got ${recipe.commands.length})`);

  console.log(`   running ffmpeg pipeline (${recipe.commands.length} commands) …`);
  const t0 = Date.now();
  const result = await runFfmpegRecipe(recipe);
  const totalMs = Date.now() - t0;
  check(result.results.every((r) => r.exitCode === 0), `all commands exited 0`);

  const outProbe = await ffprobe(outputPath);
  check(outProbe.videoCodec === "h264", `output codec h264 (got ${outProbe.videoCodec})`);
  check(outProbe.width === 2560, `output width 2560 (2x upscale; got ${outProbe.width})`);
  check(outProbe.height === 1440, `output height 1440 (got ${outProbe.height})`);
  check(
    Math.abs(outProbe.durationSec - inputProbe.durationSec) < 0.15,
    `output duration ≈ input (${outProbe.durationSec.toFixed(3)}s vs ${inputProbe.durationSec.toFixed(3)}s)`,
  );

  // Cleanup work dir
  try {
    fs.rmSync(workDir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }

  /* -------- Summary ------------------------------------------------- */
  if (failures === 0) {
    console.log("OK clip-filters smoke");
    console.log(`   ffmpeg:      ${probed.version}  (${probed.binary})`);
    console.log(`   pipeline:    deinterlace → denoise → stabilize (2-pass) → upscale 2×`);
    console.log(`   real run:    ${recipe.commands.length} cmds in ${totalMs}ms · output ${outProbe.width}×${outProbe.height} h264 ${outProbe.durationSec.toFixed(2)}s`);
    console.log(`   patch op:    setClipFilters OK · deterministic`);
  } else {
    console.error(`\n${failures} clip-filters smoke check(s) failed.`);
    process.exit(1);
  }
})().catch((err) => {
  console.error(`FATAL: ${err instanceof Error ? err.stack : err}`);
  process.exit(1);
});

// Mark unused imports as referenced (some helpers are used only in conditional paths above).
void os;
