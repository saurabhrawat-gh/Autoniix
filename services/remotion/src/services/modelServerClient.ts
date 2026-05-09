/**
 * Phase 2C — Model-server client.
 *
 * Routes GPU filters (RIFE, SCUNet, Real-ESRGAN, DDColor) to a remote
 * inference service over HTTP. The protocol is intentionally simple:
 *
 *   POST  /jobs                  → submit { kind, inputUrl, params }, returns { jobId }
 *   GET   /jobs/:jobId           → returns { status, outputUrl?, error? }
 *   POST  /jobs/:jobId/cancel    → best-effort cancellation
 *   GET   /healthz               → readiness probe
 *
 * The server keeps a content-addressed cache keyed by sha256(inputUrl,kind,params).
 * On cache hit it returns the cached `outputUrl` immediately with status="done".
 *
 * Operating modes:
 *   • Real mode    — `MODEL_SERVER_URL` env set; client makes real HTTP calls
 *                    and polls until status="done" or timeout.
 *   • Stub mode    — env unset; every request returns a deterministic
 *                    `{ status: "unavailable", fallback: <cpuKind> }` so the
 *                    orchestrator can route to the CPU equivalent.
 *
 * Stub mode is what makes this client unit-testable without a GPU. The
 * production path (real mode) is exercised by the GPU host's integration
 * suite, NOT by smoke tests.
 */

import type { ClipFilter } from "../registry/clipFilters";
import { metrics } from "../utils/metrics";

/* ====================================================================== */
/* Public types                                                           */
/* ====================================================================== */

export type ModelKind = "rife" | "scunet" | "real-esrgan" | "ddcolor";

export interface ModelJobRequest {
  kind: ModelKind;
  /** URL the model server will fetch the source from (typically a presigned MinIO URL). */
  inputUrl: string;
  /** sha256 of the input file (for cache key + integrity verification on the server). */
  inputSha256: string;
  /** Free-form parameters (model-specific). */
  params: Record<string, unknown>;
}

export type ModelJobStatus =
  | { status: "queued"; jobId: string }
  | { status: "running"; jobId: string; progress?: number }
  | { status: "done"; jobId: string; outputUrl: string; outputSha256: string }
  | { status: "failed"; jobId: string; error: string }
  | { status: "unavailable"; fallback: string };

export interface SubmitResult {
  jobId: string;
}

/* ====================================================================== */
/* Client implementation                                                  */
/* ====================================================================== */

export interface ModelServerClient {
  submit(req: ModelJobRequest): Promise<SubmitResult | ModelJobStatus>;
  poll(jobId: string): Promise<ModelJobStatus>;
  /** High-level helper: submit + poll until terminal state or timeout. */
  run(req: ModelJobRequest, opts?: RunOpts): Promise<ModelJobStatus>;
  /** Healthcheck — returns false in stub mode. */
  ping(): Promise<boolean>;
  /** Convenience: tell whether we're in stub mode. */
  isStub(): boolean;
}

export interface RunOpts {
  /** Total wall-clock budget. Default 10 minutes. */
  timeoutMs?: number;
  /** Poll interval. Default 2000ms. */
  pollIntervalMs?: number;
  /** Optional onProgress callback for UI / logs. */
  onProgress?: (s: ModelJobStatus) => void;
}

/* ---------- Stub client (no env var set) ---------------------------- */

const FALLBACK_BY_KIND: Record<ModelKind, string> = {
  rife: "blend", // warp falls back to setpts/blend
  scunet: "ffmpeg-hqdn3d", // denoise CPU equivalent
  "real-esrgan": "ffmpeg-lanczos", // upscale CPU equivalent
  ddcolor: "none", // no CPU equivalent for colorize → will fail upstream
};

class StubModelServerClient implements ModelServerClient {
  isStub(): boolean {
    return true;
  }
  async ping(): Promise<boolean> {
    return false;
  }
  async submit(req: ModelJobRequest): Promise<ModelJobStatus> {
    metrics.cache.miss("blend"); // generic miss tag — caller refines
    return { status: "unavailable", fallback: FALLBACK_BY_KIND[req.kind] };
  }
  async poll(_jobId: string): Promise<ModelJobStatus> {
    return { status: "unavailable", fallback: "stub" };
  }
  async run(req: ModelJobRequest): Promise<ModelJobStatus> {
    return this.submit(req) as Promise<ModelJobStatus>;
  }
}

/* ---------- Real HTTP client ---------------------------------------- */

class HttpModelServerClient implements ModelServerClient {
  constructor(
    private readonly baseUrl: string,
    private readonly authToken?: string,
  ) {}

  isStub(): boolean {
    return false;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "content-type": "application/json" };
    if (this.authToken) h["authorization"] = `Bearer ${this.authToken}`;
    return h;
  }

  async ping(): Promise<boolean> {
    try {
      const r = await fetch(`${this.baseUrl}/healthz`, { headers: this.headers() });
      return r.ok;
    } catch {
      return false;
    }
  }

  async submit(req: ModelJobRequest): Promise<SubmitResult | ModelJobStatus> {
    const r = await fetch(`${this.baseUrl}/jobs`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(req),
    });
    if (!r.ok) throw new Error(`model server submit failed: HTTP ${r.status}`);
    const body = (await r.json()) as { jobId: string; status?: string; outputUrl?: string; outputSha256?: string };
    // Cache hit → server returns terminal state immediately
    if (body.status === "done" && body.outputUrl) {
      return {
        status: "done",
        jobId: body.jobId,
        outputUrl: body.outputUrl,
        outputSha256: body.outputSha256 ?? "",
      };
    }
    return { jobId: body.jobId };
  }

  async poll(jobId: string): Promise<ModelJobStatus> {
    const r = await fetch(`${this.baseUrl}/jobs/${jobId}`, { headers: this.headers() });
    if (!r.ok) throw new Error(`model server poll failed: HTTP ${r.status}`);
    return (await r.json()) as ModelJobStatus;
  }

  async run(req: ModelJobRequest, opts: RunOpts = {}): Promise<ModelJobStatus> {
    const timeout = opts.timeoutMs ?? 10 * 60 * 1000;
    const interval = opts.pollIntervalMs ?? 2000;
    const start = Date.now();

    const submitted = await this.submit(req);
    // If the server already replied with a terminal state (cache hit), forward it.
    if ("status" in submitted) {
      opts.onProgress?.(submitted);
      return submitted;
    }
    const jobId = submitted.jobId;

    // Poll loop
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (Date.now() - start > timeout) {
        return { status: "failed", jobId, error: `timeout after ${timeout}ms` };
      }
      await sleep(interval);
      const s = await this.poll(jobId);
      opts.onProgress?.(s);
      if (s.status === "done" || s.status === "failed" || s.status === "unavailable") {
        return s;
      }
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/* ====================================================================== */
/* Factory                                                                */
/* ====================================================================== */

let _singleton: ModelServerClient | null = null;

/**
 * Returns the process-wide model-server client. Stub when MODEL_SERVER_URL
 * is unset; real HTTP client otherwise.
 */
export function getModelServerClient(): ModelServerClient {
  if (_singleton) return _singleton;
  const url = process.env.MODEL_SERVER_URL;
  if (!url) {
    _singleton = new StubModelServerClient();
  } else {
    _singleton = new HttpModelServerClient(url, process.env.MODEL_SERVER_TOKEN);
  }
  return _singleton;
}

/** Test hook — reset the singleton (NOT used in production code). */
export function _resetModelServerClient(): void {
  _singleton = null;
}

/* ====================================================================== */
/* Helpers: filter → ModelJobRequest                                       */
/* ====================================================================== */

/**
 * Convert a GPU-class `ClipFilter` to a `ModelJobRequest`. Throws when the
 * filter is not GPU-routed (programmer error).
 */
export function filterToModelRequest(
  filter: ClipFilter,
  inputUrl: string,
  inputSha256: string,
): ModelJobRequest {
  switch (filter.kind) {
    case "warp":
      if ((filter.interp ?? "blend") !== "rife") {
        throw new Error("filterToModelRequest: warp.interp must be 'rife' for GPU routing");
      }
      return {
        kind: "rife",
        inputUrl,
        inputSha256,
        params: {
          curve: filter.curve,
          outputScale: filter.outputScale ?? 1.0,
        },
      };
    case "denoise":
      if ((filter.model ?? "ffmpeg-hqdn3d") !== "scunet") {
        throw new Error("filterToModelRequest: denoise.model must be 'scunet' for GPU routing");
      }
      return {
        kind: "scunet",
        inputUrl,
        inputSha256,
        params: { strength: filter.strength ?? 0.5 },
      };
    case "upscale":
      if ((filter.model ?? "ffmpeg-lanczos") !== "real-esrgan") {
        throw new Error("filterToModelRequest: upscale.model must be 'real-esrgan' for GPU routing");
      }
      return {
        kind: "real-esrgan",
        inputUrl,
        inputSha256,
        params: { scale: filter.scale },
      };
    case "colorize":
      return {
        kind: "ddcolor",
        inputUrl,
        inputSha256,
        params: {},
      };
    default:
      throw new Error(`filterToModelRequest: filter ${filter.kind} is not GPU-routed`);
  }
}
