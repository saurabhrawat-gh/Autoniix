/**
 * v2 API client — shared HTTP infrastructure.
 *
 * v2 auth uses HttpOnly cookies (set by the backend on login/refresh).
 * Cookies are sent automatically via credentials:'include'.
 * No auth tokens are stored in localStorage.
 *
 * Request layer (hotfix #304 / AE-263):
 *   GET requests are routed through `dedupedGet()` from `./request-cache` to
 *   coalesce in-flight duplicates and serve a short TTL cache. This neutralises
 *   the hover/scroll/remount request-storm. Mutations bypass the cache and
 *   invalidate it on completion.
 */
import { dedupedGet, invalidateCache } from '../request-cache';

export const BASE = process.env.NEXT_PUBLIC_API_URL || '';

// One-time purge: remove any legacy localStorage token keys left from old builds.
if (typeof window !== 'undefined') {
  localStorage.removeItem('dashboard_token');
  localStorage.removeItem('dashboard_token_expires');
}

export function readToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('dashboard_token');
}

let _refreshing: Promise<boolean> | null = null;

export async function refreshOnce(): Promise<boolean> {
  if (_refreshing) return _refreshing;
  _refreshing = (async () => {
    try {
      const res = await fetch(`${BASE}/api/v2/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (res.ok) return true;
      return false;
    } catch {
      return false;
    } finally {
      _refreshing = null;
    }
  })();
  return _refreshing;
}

export async function rawRequest<T = any>(path: string, opts: RequestInit = {}, _isRetry = false): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Source': 'ui',
    ...((opts.headers as Record<string, string>) || {}),
  };
  const res = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });
  if (res.status === 401) {
    if (!_isRetry) {
      const refreshed = await refreshOnce();
      if (refreshed) return rawRequest<T>(path, opts, true);
    }
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    if (body.detail === 'workspace_access_revoked' && typeof window !== 'undefined') {
      try {
        const wRes = await fetch(`${BASE}/api/v2/auth/workspaces`, { headers, credentials: 'include' });
        if (wRes.ok) {
          const wData: { data: Array<{ id: number; active: boolean }> } = await wRes.json();
          const next = wData.data.find(w => !w.active);
          if (next) {
            await fetch(`${BASE}/api/v2/auth/switch-workspace`, {
              method: 'POST', headers, credentials: 'include',
              body: JSON.stringify({ workspace_id: next.id }),
            });
            window.location.href = '/dashboard';
            throw new Error('workspace_access_revoked');
          }
        }
      } catch {}
      window.location.href = '/login?reason=no_workspace_access';
      throw new Error('workspace_access_revoked');
    }
    throw _apiError(res.status, body);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw _apiError(res.status, body);
  }
  return res.json();
}

/**
 * Build an Error that preserves the server's structured `{detail: {code, message}}`
 * shape. Without this, callers that do `e.detail.code` see undefined and
 * `e.message` becomes the literal string "[object Object]".
 */
export function _apiError(status: number, body: unknown): Error & { status: number; detail?: unknown; code?: string } {
  const b = body as Record<string, unknown> | undefined;
  const detail = b?.detail;
  let message: string;
  if (typeof detail === 'string') message = detail;
  else if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    message = (d.message as string) || (d.code as string) || (b?.error as string) || `HTTP ${status}`;
  } else {
    message = (b?.error as string) || `HTTP ${status}`;
  }
  const err = new Error(message) as Error & { status: number; detail?: unknown; code?: string };
  err.status = status;
  if (detail !== undefined) err.detail = detail;
  if (detail && typeof detail === 'object' && typeof (detail as Record<string, unknown>).code === 'string') {
    err.code = (detail as Record<string, unknown>).code as string;
  }
  return err;
}

/**
 * Cache-aware request wrapper (hotfix #304 / AE-263).
 *
 * - GET → routed through `dedupedGet()`: in-flight coalescence + 5s TTL cache.
 * - Mutations → call `rawRequest()` directly and invalidate cache on success.
 */
export async function request<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET') {
    const result = await rawRequest<T>(path, opts);
    invalidateCache();
    return result;
  }
  return dedupedGet<T>(`GET ${path}`, () => rawRequest<T>(path, opts));
}

// Session utilities
export function isLoggedIn(): boolean {
  if (typeof window === 'undefined') return false;
  return document.cookie.split(';').some(c => c.trim() === 'auth_status=1');
}

export function setToken(token: string, expiresIn?: number) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('dashboard_token', token);
  if (expiresIn) {
    localStorage.setItem('dashboard_token_expires', String(Date.now() + expiresIn * 1000));
  }
}

export function clearToken() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('dashboard_token');
  localStorage.removeItem('dashboard_token_expires');
}

// WebSocket helpers
export function wsProgress(contentId: string): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = process.env.NEXT_PUBLIC_WS_URL || `${proto}//${window.location.host}`;
  return new WebSocket(`${host}/api/ws/progress/${contentId}`);
}

export function wsEvents(): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = process.env.NEXT_PUBLIC_WS_URL || `${proto}//${window.location.host}`;
  return new WebSocket(`${host}/api/ws/events`);
}

// Legacy password-only login (used when auth.v2.enabled = FALSE).
export async function legacyLogin(password: string): Promise<void> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const b = body as Record<string, unknown>;
    throw new Error((b.detail as string) || (b.error as string) || `HTTP ${res.status}`);
  }
  const data = await res.json() as { token: string; expires_in?: number };
  setToken(data.token, data.expires_in);
}
