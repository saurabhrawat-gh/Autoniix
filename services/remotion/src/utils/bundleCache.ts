/**
 * Bundle warmup + shared cache (P0.5).
 *
 * Replaces the per-process `cachedBundle` in renderer.ts with a content-hashed
 * shared cache. When `env.BUNDLE_CACHE_DIR` is set:
 *
 *   <BUNDLE_CACHE_DIR>/<hash>/         ← Remotion bundle output (serveable)
 *   <BUNDLE_CACHE_DIR>/<hash>/.READY   ← marker file written after copy
 *
 * Workers check the marker file first; on miss they bundle locally and then
 * copy into place atomically (rename of a temp dir → final). The CronJob
 * `scripts/bundle-warmup.ts` produces these entries on deploy.
 *
 * Hash inputs (kept minimal to avoid invalidating on irrelevant changes):
 *   - All files under `src/**` matched by extensions {ts,tsx,css,json}
 *   - The pinned versions of @remotion/* in package.json
 *   - The contents of remotion.config.ts (if present)
 *
 * Hash is sha256 of a sorted concat of `<relpath>\0<sha256(file)>`.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { env } from "./env";
import { nodePrefixWebpackOverride } from "./webpackOverride";
import { logger } from "./logger";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".css", ".json"]);
const READY_MARKER = ".READY";

/** Process-local cache to skip re-validating shared cache on every render. */
let memoizedHash: string | null = null;
let memoizedBundlePath: string | null = null;

export interface BundleCacheStats {
  hash: string;
  source: "process" | "shared" | "fresh";
  bundlePath: string;
  warmMs: number;
}

/**
 * Returns a path that can be passed as `serveUrl` to Remotion. Uses the
 * shared cache when BUNDLE_CACHE_DIR is set; otherwise behaves like a
 * per-process cache.
 */
export async function getOrBuildBundle(opts?: { entryPoint?: string }): Promise<BundleCacheStats> {
  const startedAt = Date.now();
  const entryPoint = opts?.entryPoint ?? path.resolve(process.cwd(), "src/index.ts");
  const projectRoot = path.dirname(path.dirname(entryPoint)); // services/remotion/

  if (memoizedBundlePath && memoizedHash) {
    return { hash: memoizedHash, source: "process", bundlePath: memoizedBundlePath, warmMs: Date.now() - startedAt };
  }

  // Compute the bundle's content hash from the inputs.
  const hash = await hashBundleInputs(projectRoot);

  // Shared cache hit?
  if (env.BUNDLE_CACHE_DIR) {
    const shared = path.join(env.BUNDLE_CACHE_DIR, hash);
    if (await isReady(shared)) {
      memoizedHash = hash;
      memoizedBundlePath = shared;
      logger.info({ hash, shared }, "bundle cache HIT (shared)");
      return { hash, source: "shared", bundlePath: shared, warmMs: Date.now() - startedAt };
    }
  }

  // Miss → bundle locally.
  logger.info({ hash, entryPoint }, "bundle cache MISS — bundling");
  const localBundlePath = await bundle({ entryPoint, webpackOverride: nodePrefixWebpackOverride });

  // Persist into shared cache atomically (best-effort; failure is non-fatal).
  if (env.BUNDLE_CACHE_DIR) {
    try {
      await persistToShared(localBundlePath, env.BUNDLE_CACHE_DIR, hash);
      const shared = path.join(env.BUNDLE_CACHE_DIR, hash);
      memoizedHash = hash;
      memoizedBundlePath = shared;
      return { hash, source: "fresh", bundlePath: shared, warmMs: Date.now() - startedAt };
    } catch (err) {
      logger.warn({ err }, "shared bundle persist failed; using local bundle");
    }
  }

  memoizedHash = hash;
  memoizedBundlePath = localBundlePath;
  return { hash, source: "fresh", bundlePath: localBundlePath, warmMs: Date.now() - startedAt };
}

async function hashBundleInputs(projectRoot: string): Promise<string> {
  const srcDir = path.join(projectRoot, "src");
  const files: string[] = [];
  await walk(srcDir, files);
  files.sort();

  const h = crypto.createHash("sha256");
  for (const abs of files) {
    const rel = path.relative(projectRoot, abs);
    const fileHash = await sha256OfFile(abs);
    h.update(rel);
    h.update("\0");
    h.update(fileHash);
    h.update("\n");
  }

  // Pinned remotion versions are part of the bundle's output bytes.
  try {
    const pkgRaw = await fsp.readFile(path.join(projectRoot, "package.json"), "utf8");
    const pkg = JSON.parse(pkgRaw) as { dependencies?: Record<string, string> };
    const remotion = Object.entries(pkg.dependencies ?? {})
      .filter(([k]) => k === "remotion" || k.startsWith("@remotion/"))
      .sort(([a], [b]) => a.localeCompare(b));
    h.update("REMOTION_VERSIONS\n");
    for (const [k, v] of remotion) h.update(`${k}=${v}\n`);
  } catch {
    /* ignore */
  }

  // Optional remotion.config.ts.
  for (const cfg of ["remotion.config.ts", "remotion.config.js"]) {
    const p = path.join(projectRoot, cfg);
    if (fs.existsSync(p)) {
      h.update(`CONFIG:${cfg}\n`);
      h.update(await sha256OfFile(p));
      h.update("\n");
    }
  }

  return h.digest("hex");
}

async function walk(dir: string, out: string[]): Promise<void> {
  let entries: fs.Dirent[];
  try {
    entries = await fsp.readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip __fixtures__ (test data should not invalidate the bundle).
      if (entry.name === "__fixtures__" || entry.name === "__tests__") continue;
      await walk(abs, out);
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (SOURCE_EXTENSIONS.has(ext)) out.push(abs);
    }
  }
}

async function sha256OfFile(p: string): Promise<string> {
  const buf = await fsp.readFile(p);
  return crypto.createHash("sha256").update(buf).digest("hex");
}

async function isReady(dir: string): Promise<boolean> {
  try {
    await fsp.access(path.join(dir, READY_MARKER));
    return true;
  } catch {
    return false;
  }
}

async function persistToShared(localBundlePath: string, cacheRoot: string, hash: string): Promise<void> {
  await fsp.mkdir(cacheRoot, { recursive: true });
  const finalDir = path.join(cacheRoot, hash);
  if (await isReady(finalDir)) return; // someone else won the race
  const tmpDir = path.join(cacheRoot, `.${hash}.${process.pid}.${Date.now()}`);
  await fsp.cp(localBundlePath, tmpDir, { recursive: true });
  // fs.rename is atomic on the same filesystem.
  try {
    await fsp.rename(tmpDir, finalDir);
  } catch (err) {
    // Likely lost a race — verify final exists.
    if (!(await isReady(finalDir))) {
      // Final didn't appear; rethrow so caller falls back to local.
      try {
        await fsp.rm(tmpDir, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
      throw err;
    }
  }
  await fsp.writeFile(path.join(finalDir, READY_MARKER), `${hash}\n${new Date().toISOString()}\n`);
}
