/**
 * Request dedup + TTL cache for the v2 API client.
 *
 * Added in hotfix #304 (AE-263) to neutralize the dashboard request-storm
 * observed on hover/scroll/tab-focus/component-remount. Without this layer
 * the dashboard fires the same GET 5–10× within milliseconds (no
 * deduplication, no client cache, no `Cache-Control`).
 *
 * Behaviour:
 *   - In-flight coalescence: if a request with the same key is already
 *     in flight, return its promise (N callers ⇒ 1 network call).
 *   - TTL cache: if a response was fetched within `DEFAULT_TTL_MS`, return
 *     the cached value without touching the network.
 *   - Mutations bypass this layer and call `invalidateCache()` afterwards.
 *
 * Trade-off:
 *   TTL is intentionally short (5s). Long enough to absorb hover/scroll/
 *   remount storms; short enough that stale-data UX is never noticeable.
 *   Cross-tab mutations may show up to 5s of stale data — acceptable.
 *
 * This module is intentionally framework-agnostic (no React deps) so it
 * can be unit-tested under plain Node without a test runner.
 */

type CacheEntry<T = unknown> = {
  value: T;
  expiresAt: number;
};

const inFlight = new Map<string, Promise<unknown>>();
const responseCache = new Map<string, CacheEntry>();

export const DEFAULT_TTL_MS = 5_000;

export type FetchExecutor<T> = () => Promise<T>;

/**
 * Coalesce concurrent identical requests and serve from a short TTL cache.
 *
 * @param key      Stable cache key (e.g. `"GET /api/v2/workspaces"`)
 * @param executor Function that performs the actual network call
 * @param ttlMs    How long to cache a successful response (default 5s)
 */
export async function dedupedGet<T>(
  key: string,
  executor: FetchExecutor<T>,
  ttlMs: number = DEFAULT_TTL_MS,
): Promise<T> {
  const now = Date.now();

  const cached = responseCache.get(key);
  if (cached && cached.expiresAt > now) {
    return cached.value as T;
  }

  const existing = inFlight.get(key);
  if (existing) {
    return existing as Promise<T>;
  }

  const promise = (async () => {
    try {
      const value = await executor();
      responseCache.set(key, { value, expiresAt: Date.now() + ttlMs });
      return value;
    } finally {
      inFlight.delete(key);
    }
  })();
  inFlight.set(key, promise);
  return promise;
}

/**
 * Invalidate cached responses.
 *
 * - No arg → clear everything (called after any mutation as a safe default).
 * - `keyPrefix` → clear only keys starting with the prefix (future use).
 *
 * In-flight requests are NOT cancelled — they will complete and write their
 * result to the cache. Subsequent reads will use that fresh value.
 */
export function invalidateCache(keyPrefix?: string): void {
  if (!keyPrefix) {
    responseCache.clear();
    return;
  }
  for (const k of Array.from(responseCache.keys())) {
    if (k.startsWith(keyPrefix)) responseCache.delete(k);
  }
}

// --- Test-only hooks (not part of the public contract) ---------------------

/** @internal */
export function _resetCacheForTest(): void {
  responseCache.clear();
  inFlight.clear();
}

/** @internal */
export function _cacheSizeForTest(): { responses: number; inFlight: number } {
  return { responses: responseCache.size, inFlight: inFlight.size };
}
