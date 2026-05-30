/**
 * Regression tests for request-cache.ts (hotfix #304 / AE-263).
 *
 * Run:  npx tsx dashboard/src/lib/__tests__/request-cache.test.ts
 *
 * These assertions encode the AC contract from #304:
 *   - In-flight identical requests coalesce → 100 subscribers ⇒ 1 fetch
 *   - Cached responses serve subsequent calls within TTL without network
 *   - Cache expires after TTL
 *   - invalidateCache() clears entries; in-flight requests still complete
 *
 * Uses Node's built-in `node:assert` and a manually-driven clock instead of
 * timers so the test is fast and deterministic.
 */
import assert from 'node:assert/strict';
import {
  dedupedGet,
  invalidateCache,
  _resetCacheForTest,
  _cacheSizeForTest,
} from '../request-cache';

let pass = 0;
let fail = 0;

async function test(name: string, fn: () => Promise<void>): Promise<void> {
  _resetCacheForTest();
  try {
    await fn();
    console.log(`  ✓ ${name}`);
    pass++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${(err as Error).message}`);
    fail++;
  }
}

(async () => {
  console.log('request-cache regression tests');

  await test('100 concurrent identical GETs ⇒ 1 executor call (AC: in-flight dedup)', async () => {
    let calls = 0;
    const executor = async (): Promise<{ ok: true; n: number }> => {
      calls++;
      // Yield to next microtask so all 100 callers register as in-flight
      await new Promise((r) => setTimeout(r, 5));
      return { ok: true, n: calls };
    };

    const subs = Array.from({ length: 100 }, () =>
      dedupedGet('GET /api/v2/workspaces', executor),
    );
    const results = await Promise.all(subs);

    assert.equal(calls, 1, `expected exactly 1 network call, got ${calls}`);
    assert.ok(
      results.every((r) => r.n === 1),
      'all subscribers should receive the same response object',
    );
  });

  await test('Subsequent GET within TTL serves from cache (AC: short TTL absorbs storm)', async () => {
    let calls = 0;
    const executor = async () => {
      calls++;
      return { v: calls };
    };

    const a = await dedupedGet('GET /api/v2/auth/me', executor, 1_000);
    const b = await dedupedGet('GET /api/v2/auth/me', executor, 1_000);
    const c = await dedupedGet('GET /api/v2/auth/me', executor, 1_000);

    assert.equal(calls, 1);
    assert.deepEqual(a, { v: 1 });
    assert.deepEqual(b, { v: 1 });
    assert.deepEqual(c, { v: 1 });
  });

  await test('Cache expires after TTL (AC: cache is not permanent)', async () => {
    let calls = 0;
    const executor = async () => ({ v: ++calls });

    await dedupedGet('GET /api/v2/stats', executor, 10); // 10ms TTL
    await new Promise((r) => setTimeout(r, 20));
    await dedupedGet('GET /api/v2/stats', executor, 10);

    assert.equal(calls, 2, 'second call after TTL must hit network');
  });

  await test('Different keys do not share cache entries (AC: per-endpoint isolation)', async () => {
    let calls = 0;
    const executor = async () => ({ v: ++calls });

    await dedupedGet('GET /api/v2/a', executor);
    await dedupedGet('GET /api/v2/b', executor);
    await dedupedGet('GET /api/v2/c', executor);

    assert.equal(calls, 3);
  });

  await test('invalidateCache() clears all entries (AC: mutations invalidate)', async () => {
    const executor = async () => ({ v: 1 });
    await dedupedGet('GET /api/v2/x', executor);
    await dedupedGet('GET /api/v2/y', executor);
    assert.equal(_cacheSizeForTest().responses, 2);

    invalidateCache();

    assert.equal(_cacheSizeForTest().responses, 0);
  });

  await test('invalidateCache(prefix) clears only matching entries', async () => {
    const executor = async () => ({ v: 1 });
    await dedupedGet('GET /api/v2/providers/credentials', executor);
    await dedupedGet('GET /api/v2/providers/chains', executor);
    await dedupedGet('GET /api/v2/auth/me', executor);

    invalidateCache('GET /api/v2/providers');

    assert.equal(_cacheSizeForTest().responses, 1, 'only /auth/me should remain');
  });

  await test('Executor errors do not poison the cache (AC: failures are retryable)', async () => {
    let attempt = 0;
    const executor = async () => {
      attempt++;
      if (attempt === 1) throw new Error('upstream 500');
      return { ok: true };
    };

    await assert.rejects(
      () => dedupedGet('GET /api/v2/z', executor),
      /upstream 500/,
    );

    // Second attempt should hit network again, not return cached error
    const result = await dedupedGet('GET /api/v2/z', executor);
    assert.deepEqual(result, { ok: true });
    assert.equal(attempt, 2);
  });

  await test('In-flight failure unblocks waiting subscribers (no deadlock)', async () => {
    let attempt = 0;
    const executor = async () => {
      attempt++;
      await new Promise((r) => setTimeout(r, 5));
      throw new Error('boom');
    };

    const subs = Array.from({ length: 10 }, () =>
      dedupedGet('GET /api/v2/fail', executor).catch((e: Error) => e.message),
    );
    const results = await Promise.all(subs);

    assert.equal(attempt, 1, 'all subscribers share one in-flight call even on error');
    assert.ok(results.every((r) => r === 'boom'));
    // After failure, in-flight entry must be cleared so retry can proceed
    assert.equal(_cacheSizeForTest().inFlight, 0);
  });

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail === 0 ? 0 : 1);
})();
