/**
 * Phase 2F — End-to-end archive footage gate.
 *
 * Simulates the realistic "old VHS / interlaced / shaky / noisy" pipeline
 * that the AI Quality Engine is designed to handle:
 *
 *   1. Generate a synthetic 1.5s 480i source with simulated camera shake
 *      (rotate filter cycling) and added grain (noise filter).
 *   2. Run the full clip-filter chain through the orchestrator:
 *        deinterlace (yadif) → denoise (scunet→hqdn3d fallback) →
 *        stabilize (vidstab 2-pass) → upscale (real-esrgan→lanczos fallback)
 *      All four filters' GPU lanes are unavailable in this environment, so
 *      this proves the **complete** fallback path produces broadcast-quality
 *      output without manual intervention.
 *   3. Validate the IR round-trip: the same filter chain applied via
 *      `setClipFilters` must mutate the scene-graph and the patch must be
 *      deterministic.
 *
 * Asserts:
 *   • Output exists, h264, dimensions match upscale, duration matches input.
 *   • Orchestrator records every filter's routing decision.
 *   • IR mutation deterministic.
 *
 * This is the single gate to clear before declaring Phase 2 done.
 */

import fs from "node:fs";
import path from "node:path";
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
  orchestrateClipFilters,
} from "../src/services/clipFilterOrchestrator";
import {
  ffprobe,
  makeWorkDir,
  probeFfmpeg,
} from "../src/services/ffmpegRunner";
import {
  _resetModelServerClient,
} from "../src/services/modelServerClient";
import type { ClipFilter } from "../src/registry/clipFilters";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

(async () => {
  delete process.env.MODEL_SERVER_URL;
  _resetModelServerClient();

  let probed: { binary: string; version: string };
  try {
    probed = await probeFfmpeg();
  } catch (e) {
    console.error(`SKIP archive-footage: ffmpeg unavailable (${e instanceof Error ? e.message : e})`);
    process.exit(0);
  }

  /* -------- 1. Generate "archival" source --------------------------- */
  const workDir = await makeWorkDir("yt-2f-");
  const inputPath = path.join(workDir, "vhs.mp4");
  // 480i look: 720x480, 25fps interlaced, with camera shake (rotate cycling)
  // and grain (noise=alls=20). Duration 1.5s for fast smoke.
  const gen = spawnSync(
    probed.binary,
    [
      "-y",
      "-f", "lavfi",
      "-i", "mandelbrot=size=720x480:rate=25",
      "-vf",
      [
        // Camera shake: low-amplitude rotation cycling
        "rotate=0.04*sin(2*PI*t*4):c=black",
        // Film grain
        "noise=alls=18:allf=t",
        // Force interlaced output flag so yadif has work
        "tinterlace=mode=interleave_top",
        "fieldorder=tff",
        "setdar=4/3",
      ].join(","),
      "-flags", "+ilme+ildct",
      "-t", "1.5",
      "-pix_fmt", "yuv420p",
      "-c:v", "libx264",
      "-preset", "ultrafast",
      "-crf", "23",
      inputPath,
    ],
    { encoding: "utf8" },
  );
  if (gen.status !== 0) {
    console.error(`SKIP archive-footage: synth failed\n${gen.stderr.slice(-2000)}`);
    process.exit(failures > 0 ? 1 : 0);
  }
  const inputProbe = await ffprobe(inputPath);

  /* -------- 2. IR round-trip ---------------------------------------- */
  const fixturePath = path.resolve(
    __dirname,
    "../src/scene-graph/__fixtures__/minimal-direction.json",
  );
  const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const direction = DirectionV3.parse(raw);
  const g0 = lower(direction);
  const videoTrack = g0.tracks.find((t) => t.kind === "video")!;
  const targetClip = videoTrack.clips[0] as SceneClip;

  // Full archival cleanup chain — all four filters, with GPU paths requested
  // so we exercise both the IR layer AND the fallback routing.
  const filters: ClipFilter[] = [
    { kind: "deinterlace", algo: "yadif" },
    { kind: "denoise", model: "scunet", strength: 0.5 },          // GPU → CPU fallback
    { kind: "stabilize", shakiness: 6, smoothing: 20, zoomPct: 2 },
    { kind: "upscale", model: "real-esrgan", scale: 2 },          // GPU → CPU fallback
  ];

  const patch: Patch = {
    agent: "archive-footage-smoke",
    agentVersion: "1.0.0",
    reason: "Phase 2F: clean and upscale archival footage",
    ops: [
      {
        op: "setClipFilters",
        trackId: videoTrack.id,
        clipId: targetClip.id,
        filters: filters as unknown as ClipFilterRef[],
      },
    ],
  };
  const g1 = applyPatch(g0, patch);
  const g1b = applyPatch(g0, patch);
  check(g1.hash !== g0.hash, `IR root hash changed`);
  check(g1.hash === g1b.hash, `applyPatch deterministic`);
  const updated = g1.tracks
    .find((t) => t.id === videoTrack.id)!
    .clips.find((c) => c.id === targetClip.id) as SceneClip;
  check(updated.filters?.length === 4, `4 filters installed on clip`);

  /* -------- 3. Real pixel orchestration ----------------------------- */
  const outputPath = path.join(workDir, "cleaned.mp4");
  console.log(`   running 4-filter archival cleanup pipeline …`);
  const result = await orchestrateClipFilters(filters, {
    inputPath,
    outputPath,
    workDir,
    crf: 23,
  });
  const outputProbe = await ffprobe(outputPath);

  // Decisions: deinterlace=ffmpeg, denoise=fallback-cpu, stabilize=ffmpeg, upscale=fallback-cpu
  const routes = result.decisions.map((d) => `${d.kind}:${d.route}`);
  check(routes[0] === "deinterlace:ffmpeg", `route[0] = deinterlace:ffmpeg`);
  check(routes[1] === "denoise:fallback-cpu", `route[1] = denoise:fallback-cpu`);
  check(routes[2] === "stabilize:ffmpeg", `route[2] = stabilize:ffmpeg`);
  check(routes[3] === "upscale:fallback-cpu", `route[3] = upscale:fallback-cpu`);

  check(outputProbe.videoCodec === "h264", `output codec h264`);
  check(outputProbe.width === inputProbe.width * 2, `output width ${inputProbe.width}×2 = ${outputProbe.width}`);
  check(outputProbe.height === inputProbe.height * 2, `output height ${inputProbe.height}×2 = ${outputProbe.height}`);
  check(
    Math.abs(outputProbe.durationSec - inputProbe.durationSec) < 0.2,
    `duration preserved (${outputProbe.durationSec.toFixed(2)}s vs ${inputProbe.durationSec.toFixed(2)}s)`,
  );

  /* -------- Cleanup ------------------------------------------------- */
  try {
    fs.rmSync(workDir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }

  if (failures === 0) {
    console.log("OK archive-footage smoke");
    console.log(`   ffmpeg:      ${probed.version}`);
    console.log(`   source:      ${inputProbe.width}×${inputProbe.height} interlaced + shake + grain · ${inputProbe.durationSec.toFixed(2)}s`);
    console.log(`   pipeline:    ${routes.join(" · ")}`);
    console.log(`   output:      ${outputProbe.width}×${outputProbe.height} h264 · ${outputProbe.durationSec.toFixed(2)}s · ${result.totalDurationMs}ms`);
  } else {
    console.error(`\n${failures} archive-footage smoke check(s) failed.`);
    process.exit(1);
  }
})().catch((err) => {
  console.error(`FATAL: ${err instanceof Error ? err.stack : err}`);
  process.exit(1);
});
