import "dotenv/config";

function str(key: string, fallback?: string): string {
  const v = process.env[key];
  if (v === undefined || v === "") {
    if (fallback !== undefined) return fallback;
    throw new Error(`Missing required env var: ${key}`);
  }
  return v;
}

function num(key: string, fallback: number): number {
  const v = process.env[key];
  if (v === undefined || v === "") return fallback;
  const n = Number(v);
  if (Number.isNaN(n)) throw new Error(`Invalid number for env var ${key}: ${v}`);
  return n;
}

function bool(key: string, fallback: boolean): boolean {
  const v = process.env[key];
  if (v === undefined || v === "") return fallback;
  return v === "true" || v === "1";
}

export const env = {
  NODE_ENV: str("NODE_ENV", "development"),
  API_PORT: num("API_PORT", 4000),
  LOG_LEVEL: str("LOG_LEVEL", "info"),

  REDIS_HOST: str("REDIS_HOST", "localhost"),
  REDIS_PORT: num("REDIS_PORT", 6379),
  REDIS_PASSWORD: str("REDIS_PASSWORD", ""),

  RENDER_CONCURRENCY: num("RENDER_CONCURRENCY", 1),
  RENDER_TMP_DIR: str("RENDER_TMP_DIR", "./tmp"),
  /** Worker role. Selects which queue this process consumes. P0.11. */
  WORKER_ROLE: str("WORKER_ROLE", "legacy"), // "legacy" | "tier0" | "tier1" | "tier2" | "concat"

  S3_ENDPOINT: str("S3_ENDPOINT", ""),
  S3_REGION: str("S3_REGION", "auto"),
  S3_BUCKET: str("S3_BUCKET", "yt-automation-renders"),
  S3_ACCESS_KEY_ID: str("S3_ACCESS_KEY_ID", ""),
  S3_SECRET_ACCESS_KEY: str("S3_SECRET_ACCESS_KEY", ""),
  S3_PUBLIC_BASE_URL: str("S3_PUBLIC_BASE_URL", ""),
  S3_FORCE_PATH_STYLE: bool("S3_FORCE_PATH_STYLE", true),
  S3_KEY_PREFIX: str("S3_KEY_PREFIX", ""),

  // Remotion Vision P0 flags
  /** Enable scene-graph aware path: lower direction-v3 → SceneGraph → render. */
  SCENE_GRAPH_ENABLED: bool("SCENE_GRAPH_ENABLED", false),
  /** Enable frame-range sharding via BullMQ FlowProducer. */
  SHARDING_ENABLED: bool("SHARDING_ENABLED", false),
  /** Target shard count per render. */
  SHARDING_TARGET: num("SHARDING_TARGET", 4),
  /** Enable diff-cache shard lookup before dispatch. */
  DIFF_CACHE_ENABLED: bool("DIFF_CACHE_ENABLED", false),
  /** Shared bundle directory for warm-pool reuse. Empty = per-process cache. */
  BUNDLE_CACHE_DIR: str("BUNDLE_CACHE_DIR", ""),
  /** Hardware encoder hint: "auto" | "nvenc" | "qsv" | "vaapi" | "x264". */
  ENCODER_HINT: str("ENCODER_HINT", "auto"),
};

export type Env = typeof env;
