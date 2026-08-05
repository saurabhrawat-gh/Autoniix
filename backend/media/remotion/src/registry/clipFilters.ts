/**
 * Phase 2 — Source-side clip filters (deinterlace, stabilize, warp, denoise,
 * upscale, colorize).
 *
 * Filters are applied to the *source asset* before it's rendered into the
 * timeline. The renderer treats a filtered clip as a derived asset whose
 * URL is determined by hashing `(originalSha256, filters[], schemaVersion)`
 * and looked up in `clip_render_cache` (Phase 1E).
 *
 * Two execution lanes:
 *
 *   • CPU lane (ffmpeg subprocess) — `deinterlace`, `stabilize`, fallback
 *     paths for `denoise`/`upscale` (`hqdn3d` / `lanczos`). Runs today on
 *     any host with ffmpeg ≥ 4.4 + libvidstab.
 *
 *   • GPU lane (model server) — `warp.rife`, `denoise.scunet`,
 *     `upscale.real-esrgan`, `colorize.ddcolor`. Routed through the Phase 2C
 *     queue. When `MODEL_SERVER_URL` isn't set, those kinds throw so the
 *     orchestrator falls back to CPU equivalents (deterministic).
 *
 * Order of operations matters and is fixed at recipe-build time:
 *   1. deinterlace  (must come first; downstream filters assume progressive)
 *   2. denoise
 *   3. stabilize    (denoise before stabilize: less false motion)
 *   4. colorize
 *   5. upscale
 *   6. warp         (last: speed ramps re-time the result)
 */

/* ====================================================================== */
/* Types                                                                  */
/* ====================================================================== */

export type DeinterlaceAlgo = "yadif" | "bwdif";

export interface DeinterlaceFilter {
  kind: "deinterlace";
  algo?: DeinterlaceAlgo;
}

export interface StabilizeFilter {
  kind: "stabilize";
  /** 1..10 (libvidstab `shakiness`). Default 5. */
  shakiness?: number;
  /** 0..30 (libvidstab `smoothing`). Default 15. */
  smoothing?: number;
  /** Optional zoom to hide black borders (0..10 %). Default 0. */
  zoomPct?: number;
}

/**
 * Speed curve over the source clip's [0..1] timeline. A piecewise-linear curve
 * mapping `srcU` (0..1) → `outU` (0..1). Both endpoints must be present and
 * pin to (0,0) and (1,1) for the warp to round-trip duration; intermediate
 * keys describe the ramp.
 */
export interface SpeedCurveKey {
  srcU: number;
  outU: number;
}

export interface WarpFilter {
  kind: "warp";
  curve: SpeedCurveKey[];
  /** How to invent in-between frames. Default "blend". */
  interp?: "duplicate" | "blend" | "rife";
  /** Output duration multiplier (e.g. 0.5 → half-speed → 2× length). */
  outputScale?: number;
}

export type DenoiseModel = "scunet" | "ffmpeg-hqdn3d";

export interface DenoiseFilter {
  kind: "denoise";
  model?: DenoiseModel;
  /** 0..1 strength. Default 0.5. */
  strength?: number;
}

export type UpscaleModel = "real-esrgan" | "ffmpeg-lanczos";

export interface UpscaleFilter {
  kind: "upscale";
  model?: UpscaleModel;
  scale: 2 | 3 | 4;
}

export interface ColorizeFilter {
  kind: "colorize";
  model: "ddcolor";
}

export type ClipFilter =
  | DeinterlaceFilter
  | StabilizeFilter
  | WarpFilter
  | DenoiseFilter
  | UpscaleFilter
  | ColorizeFilter;

/* ====================================================================== */
/* Validation + ordering                                                  */
/* ====================================================================== */

const ORDER: ClipFilter["kind"][] = [
  "deinterlace",
  "denoise",
  "stabilize",
  "colorize",
  "upscale",
  "warp",
];

/**
 * Returns a copy of `filters` sorted by ORDER. Throws if duplicate kinds
 * appear (a clip can have at most one of each).
 */
export function orderFilters(filters: ClipFilter[]): ClipFilter[] {
  const seen = new Set<string>();
  for (const f of filters) {
    if (seen.has(f.kind)) {
      throw new Error(`clip filters: duplicate kind "${f.kind}"`);
    }
    seen.add(f.kind);
  }
  const idx: Record<string, number> = {};
  ORDER.forEach((k, i) => (idx[k] = i));
  return [...filters].sort((a, b) => idx[a.kind]! - idx[b.kind]!);
}

export function validateFilter(f: ClipFilter, ctx = "filter"): void {
  switch (f.kind) {
    case "deinterlace":
      if (f.algo && f.algo !== "yadif" && f.algo !== "bwdif") {
        throw new Error(`${ctx}: deinterlace.algo must be yadif|bwdif`);
      }
      return;
    case "stabilize":
      if (f.shakiness !== undefined && (f.shakiness < 1 || f.shakiness > 10)) {
        throw new Error(`${ctx}: stabilize.shakiness ∈ [1,10]`);
      }
      if (f.smoothing !== undefined && (f.smoothing < 0 || f.smoothing > 30)) {
        throw new Error(`${ctx}: stabilize.smoothing ∈ [0,30]`);
      }
      if (f.zoomPct !== undefined && (f.zoomPct < 0 || f.zoomPct > 10)) {
        throw new Error(`${ctx}: stabilize.zoomPct ∈ [0,10]`);
      }
      return;
    case "warp": {
      if (f.curve.length < 2) {
        throw new Error(`${ctx}: warp.curve needs ≥ 2 keys`);
      }
      const first = f.curve[0]!;
      const last = f.curve[f.curve.length - 1]!;
      if (first.srcU !== 0 || first.outU !== 0) {
        throw new Error(`${ctx}: warp.curve must start at (0,0)`);
      }
      if (last.srcU !== 1 || last.outU !== 1) {
        throw new Error(`${ctx}: warp.curve must end at (1,1)`);
      }
      let prev = -Infinity;
      for (const k of f.curve) {
        if (k.srcU < 0 || k.srcU > 1 || k.outU < 0 || k.outU > 1) {
          throw new Error(`${ctx}: warp.curve keys ∈ [0,1]`);
        }
        if (k.srcU < prev) {
          throw new Error(`${ctx}: warp.curve srcU must be monotonic`);
        }
        prev = k.srcU;
      }
      if (f.outputScale !== undefined && (f.outputScale <= 0 || f.outputScale > 100)) {
        throw new Error(`${ctx}: warp.outputScale must be in (0,100]`);
      }
      return;
    }
    case "denoise":
      if (f.strength !== undefined && (f.strength < 0 || f.strength > 1)) {
        throw new Error(`${ctx}: denoise.strength ∈ [0,1]`);
      }
      return;
    case "upscale":
      if (f.scale !== 2 && f.scale !== 3 && f.scale !== 4) {
        throw new Error(`${ctx}: upscale.scale must be 2|3|4`);
      }
      return;
    case "colorize":
      if (f.model !== "ddcolor") {
        throw new Error(`${ctx}: colorize.model must be ddcolor`);
      }
      return;
  }
}

export function validateFilters(filters: ClipFilter[], ctx = "filters"): void {
  for (const f of filters) validateFilter(f, ctx);
  orderFilters(filters);
}

/* ====================================================================== */
/* Speed curve evaluation (used by Phase 2A)                              */
/* ====================================================================== */

/**
 * Maps an output normalized time `outU ∈ [0..1]` back to the source
 * normalized time `srcU` by inverting the piecewise-linear curve. Used by
 * the warp recipe to emit ffmpeg `setpts` / per-frame interpolation.
 */
export function srcTimeAtOutTime(curve: SpeedCurveKey[], outU: number): number {
  if (outU <= 0) return 0;
  if (outU >= 1) return 1;
  for (let i = 0; i < curve.length - 1; i++) {
    const a = curve[i]!;
    const b = curve[i + 1]!;
    if (outU >= a.outU && outU <= b.outU) {
      const span = b.outU - a.outU;
      if (span <= 1e-9) return a.srcU;
      const t = (outU - a.outU) / span;
      return a.srcU + t * (b.srcU - a.srcU);
    }
  }
  return 1;
}

/**
 * Forward map: source `srcU` → output `outU`.
 */
export function outTimeAtSrcTime(curve: SpeedCurveKey[], srcU: number): number {
  if (srcU <= 0) return 0;
  if (srcU >= 1) return 1;
  for (let i = 0; i < curve.length - 1; i++) {
    const a = curve[i]!;
    const b = curve[i + 1]!;
    if (srcU >= a.srcU && srcU <= b.srcU) {
      const span = b.srcU - a.srcU;
      if (span <= 1e-9) return a.outU;
      const t = (srcU - a.srcU) / span;
      return a.outU + t * (b.outU - a.outU);
    }
  }
  return 1;
}

/* ====================================================================== */
/* ffmpeg recipe builder (CPU lane only)                                  */
/* ====================================================================== */

export interface FfmpegRecipe {
  /** Ordered ffmpeg commands. Stabilize requires two passes → two entries. */
  commands: FfmpegCommand[];
  /** Filters that need GPU model server (caller routes them separately). */
  gpuFilters: ClipFilter[];
}

export interface FfmpegCommand {
  /** Argv (without the leading `ffmpeg`) — for safe subprocess spawn. */
  args: string[];
  /** Human-readable summary for logs. */
  summary: string;
  /** True if this command writes the *final* derived asset. */
  finalOutput: boolean;
}

export interface RecipeOptions {
  inputPath: string;
  outputPath: string;
  /** Working directory for intermediate files (stabilize transforms.trf, etc). */
  workDir: string;
  /** Encoder. Default `libx264`. */
  videoCodec?: string;
  /** CRF. Default 18 (visually lossless-ish). */
  crf?: number;
  /**
   * Source duration in seconds. REQUIRED when the recipe contains a multi-key
   * `warp` (used to compute trim ranges); ignored otherwise.
   */
  inputDurationSec?: number;
}

/**
 * Builds the ffmpeg pipeline for `filters`. GPU-routed filters are returned
 * separately in `gpuFilters` so the orchestrator can call the model server
 * for them (in the same canonical order — see ORDER above).
 */
export function buildFfmpegRecipe(
  filters: ClipFilter[],
  opts: RecipeOptions,
): FfmpegRecipe {
  validateFilters(filters);
  const ordered = orderFilters(filters);

  const gpuFilters: ClipFilter[] = [];
  const cpuFilters: ClipFilter[] = [];
  for (const f of ordered) {
    if (isGpuFilter(f)) gpuFilters.push(f);
    else cpuFilters.push(f);
  }

  const codec = opts.videoCodec ?? "libx264";
  const crf = opts.crf ?? 18;

  const warp = cpuFilters.find((f): f is WarpFilter => f.kind === "warp");
  if (warp && warp.curve.length > 2) {
    if (cpuFilters.length > 1) {
      throw new Error(
        `clip filters: multi-key warp must be the only filter in a recipe (got ${cpuFilters
          .map((f) => f.kind)
          .join(", ")}). Split into two recipes: filters first, warp second.`,
      );
    }
    return buildWarpFilterComplex(warp, opts, codec, crf, gpuFilters);
  }

  const stab = cpuFilters.find((f): f is StabilizeFilter => f.kind === "stabilize");
  const stabIdx = cpuFilters.findIndex((f) => f.kind === "stabilize");
  const preStab = stabIdx >= 0 ? cpuFilters.slice(0, stabIdx) : cpuFilters;
  const postStab = stabIdx >= 0 ? cpuFilters.slice(stabIdx + 1) : [];
  const preStabVf = preStab.map(filterToVf).filter((s): s is string => !!s);
  const postStabVf = postStab.map(filterToVf).filter((s): s is string => !!s);
  const cpuFilterChain = [...preStabVf, ...postStabVf];

  const commands: FfmpegCommand[] = [];

  if (stab) {
    const trf = `${opts.workDir}/transforms.trf`;
    const detectVf = [
      ...preStabVf,
      `vidstabdetect=shakiness=${stab.shakiness ?? 5}:result=${trf}`,
    ].join(",");
    commands.push({
      args: [
        "-y",
        "-i",
        opts.inputPath,
        "-vf",
        detectVf,
        "-f",
        "null",
        "-",
      ],
      summary: `vidstabdetect (pass 1) → ${trf}`,
      finalOutput: false,
    });

    const xformVf = [
      ...preStabVf,
      `vidstabtransform=input=${trf}:smoothing=${stab.smoothing ?? 15}:zoom=${stab.zoomPct ?? 0}`,
      "unsharp=5:5:0.8:3:3:0.4",
      ...postStabVf,
    ].join(",");
    commands.push({
      args: [
        "-y",
        "-i",
        opts.inputPath,
        "-vf",
        xformVf,
        "-c:v",
        codec,
        "-crf",
        String(crf),
        "-c:a",
        "copy",
        opts.outputPath,
      ],
      summary: `vidstabtransform (pass 2) → ${opts.outputPath}`,
      finalOutput: true,
    });
  } else if (cpuFilterChain.length > 0) {
    commands.push({
      args: [
        "-y",
        "-i",
        opts.inputPath,
        "-vf",
        cpuFilterChain.join(","),
        "-c:v",
        codec,
        "-crf",
        String(crf),
        "-c:a",
        "copy",
        opts.outputPath,
      ],
      summary: `single-pass: ${cpuFilterChain.join(",")}`,
      finalOutput: true,
    });
  } else if (gpuFilters.length === 0) {
    commands.push({
      args: ["-y", "-i", opts.inputPath, "-c", "copy", opts.outputPath],
      summary: "stream copy (no filters)",
      finalOutput: true,
    });
  }

  return { commands, gpuFilters };
}

function isGpuFilter(f: ClipFilter): boolean {
  if (f.kind === "colorize") return true;
  if (f.kind === "denoise" && (f.model ?? "ffmpeg-hqdn3d") === "scunet") return true;
  if (f.kind === "upscale" && (f.model ?? "ffmpeg-lanczos") === "real-esrgan") return true;
  if (f.kind === "warp" && (f.interp ?? "blend") === "rife") return true;
  return false;
}

/** Convert a single CPU filter to its `-vf` fragment. Returns null for GPU
 *  filters (those run via the model server). Stabilize is split-pipeline so
 *  it returns null here too — see `buildFfmpegRecipe` for the 2-pass logic. */
function filterToVf(f: ClipFilter): string | null {
  switch (f.kind) {
    case "deinterlace":
      return f.algo === "bwdif" ? "bwdif=mode=send_field:parity=auto" : "yadif=mode=1:parity=auto";
    case "denoise": {
      if ((f.model ?? "ffmpeg-hqdn3d") === "scunet") return null;
      const s = (f.strength ?? 0.5) * 8;
      return `hqdn3d=${s.toFixed(2)}:${(s * 0.75).toFixed(2)}:${(s * 1.5).toFixed(2)}:${(s * 1.0).toFixed(2)}`;
    }
    case "upscale": {
      if ((f.model ?? "ffmpeg-lanczos") === "real-esrgan") return null;
      return `scale=iw*${f.scale}:ih*${f.scale}:flags=lanczos`;
    }
    case "warp": {
      if (f.curve.length === 2) {
        const totalSpeed = (f.curve[1]!.srcU - f.curve[0]!.srcU) /
          Math.max(1e-9, f.curve[1]!.outU - f.curve[0]!.outU);
        const pts = (1 / totalSpeed).toFixed(6);
        return `setpts=${pts}*PTS`;
      }
      return null;
    }
    case "stabilize":
    case "colorize":
      return null;
  }
}

/* ---------------------------------------------------------------------- */
/* Multi-key warp via filter_complex trim+concat                          */
/* ---------------------------------------------------------------------- */

function buildWarpFilterComplex(
  warp: WarpFilter,
  opts: RecipeOptions,
  codec: string,
  crf: number,
  gpuFilters: ClipFilter[],
): FfmpegRecipe {
  const inputDur = opts.inputDurationSec;
  if (!inputDur || inputDur <= 0) {
    throw new Error(
      "buildFfmpegRecipe: multi-key warp requires opts.inputDurationSec",
    );
  }
  const outputScale = warp.outputScale ?? 1.0;
  const outputDur = inputDur * outputScale;

  const segments: string[] = [];
  const labels: string[] = [];
  for (let i = 0; i < warp.curve.length - 1; i++) {
    const a = warp.curve[i]!;
    const b = warp.curve[i + 1]!;
    const srcStart = a.srcU * inputDur;
    const srcEnd = b.srcU * inputDur;
    const outStart = a.outU * outputDur;
    const outEnd = b.outU * outputDur;
    const srcSpan = Math.max(1e-6, srcEnd - srcStart);
    const outSpan = Math.max(1e-6, outEnd - outStart);
    const ptsFactor = (outSpan / srcSpan).toFixed(6);
    const label = `wv${i}`;
    labels.push(label);
    segments.push(
      `[0:v]trim=start=${srcStart.toFixed(6)}:end=${srcEnd.toFixed(6)},setpts=${ptsFactor}*(PTS-STARTPTS)[${label}]`,
    );
  }
  const concat = `${labels.map((l) => `[${l}]`).join("")}concat=n=${labels.length}:v=1:a=0[outv]`;
  const filterComplex = [...segments, concat].join(";");

  const command: FfmpegCommand = {
    args: [
      "-y",
      "-i",
      opts.inputPath,
      "-filter_complex",
      filterComplex,
      "-map",
      "[outv]",
      "-c:v",
      codec,
      "-crf",
      String(crf),
      "-an",
      opts.outputPath,
    ],
    summary: `multi-key warp (${labels.length} segments) → ${opts.outputPath}`,
    finalOutput: true,
  };
  return { commands: [command], gpuFilters };
}
