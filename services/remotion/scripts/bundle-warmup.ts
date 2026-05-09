/**
 * Bundle warmup CLI (P0.5).
 *
 * Builds the Remotion bundle once and persists it into BUNDLE_CACHE_DIR with
 * the content hash as its directory name. Idempotent — if a ready entry
 * matching the current hash already exists, exits 0 without rebundling.
 *
 * Intended to run as:
 *   - a k8s CronJob every 10 minutes
 *   - a post-deploy hook
 *   - locally: `npm run bundle:warmup` after `git pull`
 *
 * Exit codes:
 *   0  warm cache produced or already up-to-date
 *   1  bundling failed
 *   2  shared cache could not be written (BUNDLE_CACHE_DIR not set / not writable)
 */

import { env } from "../src/utils/env";
import { getOrBuildBundle } from "../src/utils/bundleCache";

async function main() {
  if (!env.BUNDLE_CACHE_DIR) {
    console.error("BUNDLE_CACHE_DIR is not set; nothing to warm.");
    process.exit(2);
  }
  const stats = await getOrBuildBundle();
  console.log(
    JSON.stringify({
      ok: true,
      source: stats.source,
      hash: stats.hash,
      bundlePath: stats.bundlePath,
      warmMs: stats.warmMs,
    }),
  );
}

main().catch((err) => {
  console.error("bundle warmup failed:", err);
  process.exit(1);
});
