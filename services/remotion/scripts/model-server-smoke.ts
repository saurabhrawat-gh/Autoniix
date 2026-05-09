/**
 * Phase 2C–2E — Model-server client + orchestrator smoke test.
 *
 * Verifies the GPU-filter routing contract WITHOUT a real GPU host:
 *
 *   • Stub mode (MODEL_SERVER_URL unset):
 *       - `getModelServerClient().isStub() === true`
 *       - `submit()` returns { status: "unavailable", fallback: <cpuKind> }
 *       - `filterToModelRequest()` builds the right shape per kind
 *
 *   • Orchestrator end-to-end:
 *       - GPU filters (denoise/scunet, upscale/real-esrgan) get routed to the
 *         model server, which is stubbed → orchestrator falls back to CPU
 *         equivalents and runs them via ffmpeg.
 *       - colorize/ddcolor has NO CPU fallback → orchestrator throws.
 *       - Real h264 output produced for the fallback path; codec/dimensions
 *         match expectations.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/model-server-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

import {
  filterToModelRequest,
  getModelServerClient,
  _resetModelServerClient,
} from "../src/services/modelServerClient";
import {
  orchestrateClipFilters,
} from "../src/services/clipFilterOrchestrator";
import {
  ffprobe,
  makeWorkDir,
  probeFfmpeg,
} from "../src/services/ffmpegRunner";
import type { ClipFilter } from "../src/registry/clipFilters";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

(async () => {
  // Force stub mode for the test.
  delete process.env.MODEL_SERVER_URL;
  _resetModelServerClient();

  /* ---- 1. Stub client basics --------------------------------------- */
  const client = getModelServerClient();
  check(client.isStub(), "client is in stub mode");
  check((await client.ping()) === false, "stub ping returns false");

  const stubResp = await client.submit({
    kind: "scunet",
    inputUrl: "file:///tmp/x.mp4",
    inputSha256: "a".repeat(64),
    params: { strength: 0.5 },
  });
  check(
    "status" in stubResp && stubResp.status === "unavailable",
    `stub submit returns unavailable: ${JSON.stringify(stubResp)}`,
  );

  /* ---- 2. filterToModelRequest shape tests ------------------------- */
  const denoiseReq = filterToModelRequest(
    { kind: "denoise", model: "scunet", strength: 0.7 },
    "file:///x.mp4",
    "b".repeat(64),
  );
  check(denoiseReq.kind === "scunet", `denoise → scunet`);
  check(denoiseReq.params.strength === 0.7, `denoise strength preserved`);

  const upscaleReq = filterToModelRequest(
    { kind: "upscale", model: "real-esrgan", scale: 4 },
    "file:///x.mp4",
    "c".repeat(64),
  );
  check(upscaleReq.kind === "real-esrgan", `upscale → real-esrgan`);
  check(upscaleReq.params.scale === 4, `upscale scale preserved`);

  const colorizeReq = filterToModelRequest(
    { kind: "colorize", model: "ddcolor" },
    "file:///x.mp4",
    "d".repeat(64),
  );
  check(colorizeReq.kind === "ddcolor", `colorize → ddcolor`);

  // CPU-class filters refused by filterToModelRequest
  let threw = false;
  try {
    filterToModelRequest(
      { kind: "denoise", model: "ffmpeg-hqdn3d" },
      "file:///x.mp4",
      "0".repeat(64),
    );
  } catch {
    threw = true;
  }
  check(threw, `filterToModelRequest rejects ffmpeg-hqdn3d`);

  /* ---- 3. Orchestrator: GPU filters with no GPU → CPU fallback ----- */
  let probed: { binary: string; version: string };
  try {
    probed = await probeFfmpeg();
  } catch (e) {
    console.error(
      `SKIP orchestrator end-to-end: ffmpeg unavailable (${e instanceof Error ? e.message : e})`,
    );
    if (failures > 0) process.exit(1);
    process.exit(0);
  }

  const workDir = await makeWorkDir("yt-2c-");
  const inputPath = path.join(workDir, "in.mp4");
  // 1.5s 640x360 source
  const gen = spawnSync(
    probed.binary,
    [
      "-y",
      "-f", "lavfi",
      "-i", "testsrc2=size=640x360:rate=30:duration=1.5",
      "-pix_fmt", "yuv420p",
      "-c:v", "libx264",
      "-preset", "ultrafast",
      "-crf", "23",
      inputPath,
    ],
    { encoding: "utf8" },
  );
  if (gen.status !== 0) {
    console.error(`SKIP orchestrator: failed to generate input\n${gen.stderr.slice(-1500)}`);
    process.exit(failures > 0 ? 1 : 0);
  }

  // Filters: GPU denoise + GPU upscale → both should fall back to CPU equivalents.
  const filters: ClipFilter[] = [
    { kind: "denoise", model: "scunet", strength: 0.5 },
    { kind: "upscale", model: "real-esrgan", scale: 2 },
  ];
  const outputPath = path.join(workDir, "out.mp4");
  const result = await orchestrateClipFilters(filters, {
    inputPath,
    outputPath,
    workDir,
    crf: 23,
  });
  check(result.outputPath === outputPath, `orchestrator output path`);
  check(
    result.decisions.length === 2 &&
      result.decisions.every((d) => d.route === "fallback-cpu"),
    `both filters routed to fallback-cpu (got ${JSON.stringify(result.decisions.map((d) => d.route))})`,
  );

  const probeOut = await ffprobe(outputPath);
  check(probeOut.videoCodec === "h264", `fallback output is h264`);
  check(probeOut.width === 1280, `2x upscale → 1280px width`);
  check(probeOut.height === 720, `2x upscale → 720px height`);

  /* ---- 4. Colorize has no CPU fallback → orchestrator throws -------- */
  let colorizeThrew = false;
  try {
    await orchestrateClipFilters(
      [{ kind: "colorize", model: "ddcolor" }],
      {
        inputPath,
        outputPath: path.join(workDir, "color.mp4"),
        workDir,
      },
    );
  } catch {
    colorizeThrew = true;
  }
  check(colorizeThrew, `colorize throws when GPU unavailable + no CPU fallback`);

  /* ---- Cleanup ----------------------------------------------------- */
  try {
    fs.rmSync(workDir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }

  if (failures === 0) {
    console.log("OK model-server smoke");
    console.log(`   client mode: stub (MODEL_SERVER_URL unset)`);
    console.log(`   protocol:    rife · scunet · real-esrgan · ddcolor`);
    console.log(
      `   orchestrator: GPU denoise+upscale → CPU fallback → ${probeOut.width}×${probeOut.height} h264 in ${result.totalDurationMs}ms`,
    );
    console.log(`   no fallback: colorize throws with clear message`);
  } else {
    console.error(`\n${failures} model-server smoke check(s) failed.`);
    process.exit(1);
  }
})().catch((err) => {
  console.error(`FATAL: ${err instanceof Error ? err.stack : err}`);
  process.exit(1);
});
