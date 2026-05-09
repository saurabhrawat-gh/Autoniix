/**
 * Phase 1E — Lightweight Prometheus metrics shim.
 *
 * Wraps `prom-client` lazily: if it's installed we register real Counter /
 * Histogram instruments; if not, we fall back to no-op stubs. This lets the
 * emission code in agents / renderers ship without forcing every consumer
 * to take the dependency.
 *
 * Two defaults that matter:
 *   • `MetricsRegistry` instance is shared per-process via a module-level
 *     singleton.
 *   • `getMetricsText()` returns the standard exposition format string for
 *     `/metrics` HTTP scrape; mounted by the API server as a follow-up.
 *
 * Phase 1A–1D counters are pre-declared at module load. Adding new metrics
 * later is a one-line change inside `phase1Metrics()`.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyCounter = {
  inc: (labels?: Record<string, string>, value?: number) => void;
};
type AnyHistogram = {
  observe: (labels: Record<string, string>, value: number) => void;
};

let _promClient: any = null;
let _registry: any = null;

function tryLoadPromClient(): any {
  if (_promClient !== null) return _promClient;
  try {
    // Optional dependency — must not break the build when missing.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("prom-client");
    _promClient = mod;
    _registry = new mod.Registry();
    mod.collectDefaultMetrics({ register: _registry });
    return mod;
  } catch {
    _promClient = false; // signal "tried and unavailable"
    return null;
  }
}

function makeCounter(name: string, help: string, labelNames: string[]): AnyCounter {
  const mod = tryLoadPromClient();
  if (!mod) return { inc: () => {} };
  const c = new mod.Counter({ name, help, labelNames, registers: [_registry] });
  return c as AnyCounter;
}

function makeHistogram(
  name: string,
  help: string,
  labelNames: string[],
  buckets: number[],
): AnyHistogram {
  const mod = tryLoadPromClient();
  if (!mod) return { observe: () => {} };
  const h = new mod.Histogram({ name, help, labelNames, buckets, registers: [_registry] });
  return h as AnyHistogram;
}

/* ====================================================================== */
/* Phase 1A–1D metric set                                                  */
/* ====================================================================== */

interface Phase1Metrics {
  // 1A
  blendModeUsage: AnyCounter; // labels: mode, clipKind
  blendModeShaderFallback: AnyCounter; // labels: mode

  // 1B
  textAnimRender: AnyHistogram; // labels: kind  (seconds)
  textAnimUsage: AnyCounter; // labels: kind

  // 1C
  maskRender: AnyHistogram; // labels: kind  (seconds)
  maskShaderFallback: AnyCounter; // labels: kind
  maskUsage: AnyCounter; // labels: kind, blend

  // 1D
  colorGradePass: AnyHistogram; // labels: path  ('css'|'webgl')  (seconds)
  colorGradeWebglFallback: AnyCounter; // labels: reason

  // Cache layer
  cacheHit: AnyCounter; // labels: kind  ('blend'|'mask'|'grade'|'text_anim')
  cacheMiss: AnyCounter; // labels: kind
}

let _metrics: Phase1Metrics | null = null;
function phase1Metrics(): Phase1Metrics {
  if (_metrics) return _metrics;
  _metrics = {
    blendModeUsage: makeCounter(
      "yt_blend_mode_usage_total",
      "Per-clip blend mode application count",
      ["mode", "clipKind"],
    ),
    blendModeShaderFallback: makeCounter(
      "yt_blend_mode_shader_fallback_total",
      "How often a blend mode fell to the CSS approximation because the shader path was unavailable",
      ["mode"],
    ),
    textAnimRender: makeHistogram(
      "yt_text_anim_render_duration_seconds",
      "Wall time spent computing one frame of an advanced text animation",
      ["kind"],
      [0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1],
    ),
    textAnimUsage: makeCounter(
      "yt_text_anim_usage_total",
      "Per-clip advanced text animation usage count",
      ["kind"],
    ),
    maskRender: makeHistogram(
      "yt_mask_render_duration_seconds",
      "Wall time spent computing one frame of an animated mask",
      ["kind"],
      [0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1],
    ),
    maskShaderFallback: makeCounter(
      "yt_mask_shader_fallback_total",
      "How often luma/chroma masks fell through to passthrough because the shader path was unavailable",
      ["kind"],
    ),
    maskUsage: makeCounter(
      "yt_mask_usage_total",
      "Per-clip animated mask usage count",
      ["kind", "blend"],
    ),
    colorGradePass: makeHistogram(
      "yt_color_grade_pass_duration_seconds",
      "Wall time spent applying a color grade pass",
      ["path"],
      [0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1],
    ),
    colorGradeWebglFallback: makeCounter(
      "yt_color_grade_webgl_fallback_total",
      "How often a grade requiring WebGL fell back to CSS approximation",
      ["reason"],
    ),
    cacheHit: makeCounter(
      "yt_clip_render_cache_hit_total",
      "Diff-cache hits for advanced editing features",
      ["kind"],
    ),
    cacheMiss: makeCounter(
      "yt_clip_render_cache_miss_total",
      "Diff-cache misses for advanced editing features",
      ["kind"],
    ),
  };
  return _metrics;
}

/* ====================================================================== */
/* Public API                                                              */
/* ====================================================================== */

export const metrics = {
  blendMode: {
    used: (mode: string, clipKind: string): void =>
      phase1Metrics().blendModeUsage.inc({ mode, clipKind }, 1),
    shaderFallback: (mode: string): void =>
      phase1Metrics().blendModeShaderFallback.inc({ mode }, 1),
  },
  textAnim: {
    used: (kind: string): void => phase1Metrics().textAnimUsage.inc({ kind }, 1),
    observed: (kind: string, seconds: number): void =>
      phase1Metrics().textAnimRender.observe({ kind }, seconds),
  },
  mask: {
    used: (kind: string, blend: string): void =>
      phase1Metrics().maskUsage.inc({ kind, blend }, 1),
    observed: (kind: string, seconds: number): void =>
      phase1Metrics().maskRender.observe({ kind }, seconds),
    shaderFallback: (kind: string): void =>
      phase1Metrics().maskShaderFallback.inc({ kind }, 1),
  },
  colorGrade: {
    observed: (path: "css" | "webgl", seconds: number): void =>
      phase1Metrics().colorGradePass.observe({ path }, seconds),
    webglFallback: (reason: string): void =>
      phase1Metrics().colorGradeWebglFallback.inc({ reason }, 1),
  },
  cache: {
    hit: (kind: "blend" | "mask" | "grade" | "text_anim"): void =>
      phase1Metrics().cacheHit.inc({ kind }, 1),
    miss: (kind: "blend" | "mask" | "grade" | "text_anim"): void =>
      phase1Metrics().cacheMiss.inc({ kind }, 1),
  },
};

/**
 * Returns the Prometheus exposition text. Empty string when prom-client
 * isn't installed — caller can mount this on `/metrics`.
 */
export async function getMetricsText(): Promise<string> {
  if (!tryLoadPromClient() || !_registry) return "";
  return _registry.metrics();
}

/**
 * Returns whether prom-client is actually loaded. Useful for logs at boot.
 */
export function metricsBackendActive(): boolean {
  return !!tryLoadPromClient();
}
