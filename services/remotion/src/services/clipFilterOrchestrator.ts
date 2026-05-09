/**
 * Phase 2C–2E — Clip-filter orchestrator.
 *
 * Single entry point that takes a list of `ClipFilter`s and an input video
 * URL and returns a final derived asset URL. Routing rules:
 *
 *   1. Split filters into CPU (ffmpeg) and GPU (model server) lanes.
 *   2. For each GPU filter (in canonical order): submit to model server.
 *      • Real mode → wait for the inference result; the server's outputUrl
 *        becomes the input for the next stage.
 *      • Stub mode → fall back to the corresponding CPU filter ("scunet" →
 *        "ffmpeg-hqdn3d", "real-esrgan" → "ffmpeg-lanczos", "rife" → "blend",
 *        "ddcolor" → throw because there's no CPU equivalent).
 *   3. Build a single ffmpeg recipe from the (possibly amended) CPU filter
 *      list and run it with `runFfmpegRecipe`.
 *
 * The orchestrator is *file-path based* for the smoke test path; real
 * production wiring (S3 download/upload) is documented in the prod runner.
 */

import path from "node:path";
import { promises as fs } from "node:fs";
import { createHash } from "node:crypto";
import {
  buildFfmpegRecipe,
  type ClipFilter,
} from "../registry/clipFilters";
import {
  ffprobe,
  runFfmpegRecipe,
} from "./ffmpegRunner";
import {
  filterToModelRequest,
  getModelServerClient,
} from "./modelServerClient";
import { metrics } from "../utils/metrics";

export interface OrchestrateOpts {
  inputPath: string;
  outputPath: string;
  workDir: string;
  /** Override sha256 (skips the hash-on-disk step in tests). */
  inputSha256?: string;
  /** Override input duration (skips ffprobe; required for multi-key warp). */
  inputDurationSec?: number;
  videoCodec?: string;
  crf?: number;
}

export interface OrchestrateResult {
  outputPath: string;
  totalDurationMs: number;
  /** Per-filter routing decisions for observability. */
  decisions: FilterDecision[];
}

export interface FilterDecision {
  kind: ClipFilter["kind"];
  route: "ffmpeg" | "model-server" | "fallback-cpu" | "skipped";
  durationMs?: number;
  detail?: string;
}

/* ====================================================================== */
/* Helpers                                                                */
/* ====================================================================== */

async function sha256OfFile(file: string): Promise<string> {
  const buf = await fs.readFile(file);
  return createHash("sha256").update(buf).digest("hex");
}

/** Map a GPU-failed filter to its CPU equivalent. Returns null when there is
 *  no CPU fallback (currently: colorize). */
function gpuFallbackToCpu(f: ClipFilter): ClipFilter | null {
  switch (f.kind) {
    case "warp":
      // RIFE → CPU blend = use the same warp filter without the rife flag.
      return { ...f, interp: "blend" };
    case "denoise":
      return { ...f, model: "ffmpeg-hqdn3d" };
    case "upscale":
      return { ...f, model: "ffmpeg-lanczos" };
    case "colorize":
      return null;
    default:
      return f; // not GPU-routed
  }
}

/* ====================================================================== */
/* Public orchestrator                                                    */
/* ====================================================================== */

export async function orchestrateClipFilters(
  filters: ClipFilter[],
  opts: OrchestrateOpts,
): Promise<OrchestrateResult> {
  const start = Date.now();
  const decisions: FilterDecision[] = [];

  // Compute input metadata (sha + duration) once.
  const inputSha256 = opts.inputSha256 ?? (await sha256OfFile(opts.inputPath));
  const inputDurationSec =
    opts.inputDurationSec ?? (await ffprobe(opts.inputPath)).durationSec;

  // First pass: route each filter through the model server if it's GPU-class.
  // The model server returns either a derived URL (which we'd download for
  // the next stage in production) or `unavailable` → CPU fallback. For this
  // orchestrator we currently support fallback-CPU end-to-end and document
  // the real-mode download step.
  const client = getModelServerClient();
  const cpuFilters: ClipFilter[] = [];
  for (const f of filters) {
    const isGpu =
      (f.kind === "warp" && (f.interp ?? "blend") === "rife") ||
      (f.kind === "denoise" && (f.model ?? "ffmpeg-hqdn3d") === "scunet") ||
      (f.kind === "upscale" && (f.model ?? "ffmpeg-lanczos") === "real-esrgan") ||
      f.kind === "colorize";

    if (!isGpu) {
      cpuFilters.push(f);
      decisions.push({ kind: f.kind, route: "ffmpeg" });
      continue;
    }

    // GPU lane.
    const t0 = Date.now();
    const req = filterToModelRequest(f, opts.inputPath, inputSha256);
    const resp = await client.run(req);
    const dt = Date.now() - t0;

    if (resp.status === "done") {
      // Real-mode happy path — the server returned a derived asset. The next
      // stage would download `resp.outputUrl` and use it as the new input.
      // For the smoke-testable path (CPU host, stub mode) we never hit this
      // branch; production runners must implement the download.
      decisions.push({
        kind: f.kind,
        route: "model-server",
        durationMs: dt,
        detail: `outputUrl=${resp.outputUrl}`,
      });
      throw new Error(
        `orchestrateClipFilters: model server real-mode download not yet wired. ` +
          `Got outputUrl=${resp.outputUrl}; integrate S3/MinIO download here.`,
      );
    }

    if (resp.status === "unavailable") {
      const fallback = gpuFallbackToCpu(f);
      if (!fallback) {
        decisions.push({
          kind: f.kind,
          route: "skipped",
          detail: `no CPU fallback for ${f.kind}`,
        });
        throw new Error(
          `orchestrateClipFilters: ${f.kind} requires the GPU model server (MODEL_SERVER_URL not set, no CPU fallback)`,
        );
      }
      cpuFilters.push(fallback);
      decisions.push({
        kind: f.kind,
        route: "fallback-cpu",
        durationMs: dt,
        detail: `→ ${fallback.kind}/${describeFilter(fallback)}`,
      });
      metrics.cache.miss("blend"); // generic miss counter — we'd refine per-kind later
      continue;
    }

    // failed | other
    throw new Error(
      `orchestrateClipFilters: model server returned ${resp.status}` +
        (resp.status === "failed" ? `: ${resp.error}` : ""),
    );
  }

  // Build + run the CPU recipe.
  const recipe = buildFfmpegRecipe(cpuFilters, {
    inputPath: opts.inputPath,
    outputPath: opts.outputPath,
    workDir: opts.workDir,
    videoCodec: opts.videoCodec,
    crf: opts.crf,
    inputDurationSec,
  });
  await runFfmpegRecipe(recipe);

  return {
    outputPath: opts.outputPath,
    totalDurationMs: Date.now() - start,
    decisions,
  };
}

function describeFilter(f: ClipFilter): string {
  switch (f.kind) {
    case "denoise":
      return f.model ?? "ffmpeg-hqdn3d";
    case "upscale":
      return f.model ?? "ffmpeg-lanczos";
    case "warp":
      return f.interp ?? "blend";
    default:
      return f.kind;
  }
}
