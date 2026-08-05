/**
 * v2 API client — backwards-compat shim.
 *
 * Implementation has moved to `src/lib/api/` (AE-594 Phase 2 split).
 * This file re-exports everything so existing imports keep working.
 *
 * Prefer importing from `@/lib/api` in new code.
 */
export * from './api/index';
