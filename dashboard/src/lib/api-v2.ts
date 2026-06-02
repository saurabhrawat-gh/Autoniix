/**
 * v2 API client.
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
import { dedupedGet, invalidateCache } from './request-cache';

const BASE = process.env.NEXT_PUBLIC_API_URL || '';

// One-time purge: remove any legacy localStorage token keys left from old builds.
if (typeof window !== 'undefined') {
  localStorage.removeItem('dashboard_token');
  localStorage.removeItem('dashboard_token_expires');
}

function readToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('dashboard_token');
}

let _refreshing: Promise<boolean> | null = null;

async function refreshOnce(): Promise<boolean> {
  if (_refreshing) return _refreshing;
  _refreshing = (async () => {
    try {
      const res = await fetch(`${BASE}/api/v2/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (res.ok) {
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      _refreshing = null;
    }
  })();
  return _refreshing;
}

async function rawRequest<T = any>(path: string, opts: RequestInit = {}, _isRetry = false): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Source': 'ui',
    ...((opts.headers as Record<string, string>) || {}),
  };
  // v2 auth uses HttpOnly cookies only — no Authorization header needed
  const res = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });
  if (res.status === 401) {
    if (!_isRetry) {
      const refreshed = await refreshOnce();
      // Recurse via rawRequest (NOT the cached `request`) to avoid the
      // in-flight dedup map from waiting on the executor that owns it.
      if (refreshed) return rawRequest<T>(path, opts, true);
    }
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    if (body.detail === 'workspace_access_revoked' && typeof window !== 'undefined') {
      // Try auto-switching to next available workspace
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
      window.location.href = '/register?reason=no_workspace';
      throw new Error('workspace_access_revoked');
    }
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Cache-aware request wrapper (hotfix #304 / AE-263).
 *
 * - GET → routed through `dedupedGet()`: in-flight coalescence + 5s TTL cache.
 * - Mutations (POST/PUT/PATCH/DELETE) → call `rawRequest()` directly and
 *   invalidate the entire response cache on success. Broad-stroke
 *   invalidation is intentional: mutations are rare; the cost of one extra
 *   refetch is dwarfed by the cost of stale UI.
 *
 * All existing callers keep the same signature; the change is transparent.
 */
async function request<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET') {
    const result = await rawRequest<T>(path, opts);
    invalidateCache();
    return result;
  }
  return dedupedGet<T>(`GET ${path}`, () => rawRequest<T>(path, opts));
}

// Flags
export const flagsApi = {
  list: () => request<{ data: Array<{ key: string; enabled: boolean; description: string; payload: any }> }>('/api/v2/flags'),
  set: (key: string, enabled: boolean, payload: any = {}) =>
    request(`/api/v2/flags/${key}`, { method: 'PUT', body: JSON.stringify({ enabled, payload }) }),
};

// Auth
export const authApi = {
  mode: () =>
    fetch(`${BASE}/api/v2/auth/mode`).then(r => r.json()) as Promise<{ v2_enabled: boolean; legacy_enabled: boolean }>,
  register: (email: string, password: string, workspace_name: string, display_name?: string) =>
    request('/api/v2/auth/register', { method: 'POST', body: JSON.stringify({ email, password, workspace_name, display_name }) }),
  login: async (email: string, password: string, mfa_code?: string) => {
    // Use raw fetch — NOT the request() wrapper — so a 401 from the login
    // endpoint is surfaced as an error to the caller instead of triggering
    // the global refresh-then-redirect interceptor (which causes a silent
    // page reload with no error message).
    const res = await fetch(`${BASE}/api/v2/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Source': 'ui' },
      body: JSON.stringify({ email, password, mfa_code }),
      credentials: 'include',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data;
  },
  refresh: async (): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/api/v2/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || `HTTP ${res.status}`);
    }
    return res.json();
  },
  logout: async () => {
    clearToken();
    return request('/api/v2/auth/logout', { method: 'POST' });
  },
  me: () => request<{ data: { user_id: number | null; email: string | null; role: string; source: string; display_name: string | null; initials: string; permissions: string[] } }>('/api/v2/auth/me'),
  forgot: (email: string) =>
    request<{ reset_token?: string }>('/api/v2/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
  reset: (token: string, password: string) =>
    request('/api/v2/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) }),
  mfaSetup: () => request<{ data: { otpauth_url: string; secret: string } }>('/api/v2/auth/mfa/setup', { method: 'POST' }),
  mfaVerify: (code: string) =>
    request('/api/v2/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
  updateProfile: (data: { display_name?: string; current_password?: string; new_password?: string }) =>
    request<{ status: string; message: string }>('/api/v2/auth/profile', { method: 'PUT', body: JSON.stringify(data) }),
  deleteAccount: (password: string) =>
    request<{ status: string }>('/api/v2/auth/account', { method: 'DELETE', body: JSON.stringify({ password }) }),
  listWorkspaces: () =>
    request<{ data: Array<{ id: number; name: string; slug: string; plan: string; role: string; active: boolean; onboarding_completed: boolean }> }>('/api/v2/auth/workspaces'),
  switchWorkspace: (workspace_id: number) =>
    request<{ status: string; workspace_id: number; role: string }>(
      '/api/v2/auth/switch-workspace',
      { method: 'POST', body: JSON.stringify({ workspace_id }) }
    ),
  acceptInvite: (token: string, password?: string, display_name?: string) =>
    request<{ status: string; workspace_id: number; role: string }>(
      '/api/v2/auth/accept-invite',
      { method: 'POST', body: JSON.stringify({ token, password, display_name }) }
    ),
  createWorkspace: (workspace_name: string) =>
    request<{ status: string; workspace_id: number; role: string; access_token: string }>(
      '/api/v2/auth/create-workspace',
      { method: 'POST', body: JSON.stringify({ workspace_name }) }
    ),
};

// Channels
export const channelsApi = {
  list: (includeArchived = false) =>
    request<{ data: any[] }>(`/api/v2/channels?include_archived=${includeArchived}`),
  get: (id: string) => request<{ data: any }>(`/api/v2/channels/${id}`),
  create: (body: any) => request<{ channel_id: string }>('/api/v2/channels', { method: 'POST', body: JSON.stringify(body) }),
  patch: (id: string, body: any) => request(`/api/v2/channels/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  upsertProfile: (id: string, payload: any) =>
    request(`/api/v2/channels/${id}/profile`, { method: 'PUT', body: JSON.stringify({ payload }) }),
  presets: () => request<{ data: any[] }>('/api/v2/channels/presets'),
  addPillar: (id: string, body: any) => request(`/api/v2/channels/${id}/pillars`, { method: 'POST', body: JSON.stringify(body) }),
  deletePillar: (id: string, pid: number) => request(`/api/v2/channels/${id}/pillars/${pid}`, { method: 'DELETE' }),
  addRule: (id: string, body: any) => request(`/api/v2/channels/${id}/topic-rules`, { method: 'POST', body: JSON.stringify(body) }),
  deleteRule: (id: string, rid: number) => request(`/api/v2/channels/${id}/topic-rules/${rid}`, { method: 'DELETE' }),
  addReference: (id: string, body: any) => request(`/api/v2/channels/${id}/references`, { method: 'POST', body: JSON.stringify(body) }),
  deleteReference: (id: string, rid: number) => request(`/api/v2/channels/${id}/references/${rid}`, { method: 'DELETE' }),
  fieldSuggest: (field: string, context: any = {}) =>
    request<{ data: { suggestion: string; rationale: string } }>(
      '/api/v2/channels/ai/field-suggest',
      { method: 'POST', body: JSON.stringify({ field, context }) }
    ),
  draftCreate: (current_step: number, payload: any) =>
    request<{ id: number }>('/api/v2/channels/drafts', { method: 'POST', body: JSON.stringify({ current_step, payload }) }),
  draftSave: (id: number, current_step: number, payload: any) =>
    request(`/api/v2/channels/drafts/${id}`, { method: 'PUT', body: JSON.stringify({ current_step, payload }) }),
  draftGet: (id: number) => request<{ data: any }>(`/api/v2/channels/drafts/${id}`),
  // Wave 5: status actions
  enable:  (id: string) => request(`/api/v2/channels/${id}/enable`,  { method: 'PUT' }),
  disable: (id: string) => request(`/api/v2/channels/${id}/disable`, { method: 'PUT' }),
  archive: (id: string) => request(`/api/v2/channels/${id}/archive`, { method: 'PUT' }),
  restore: (id: string) => request(`/api/v2/channels/${id}/restore`, { method: 'PUT' }),
  clone:   (id: string) => request(`/api/v2/channels/${id}/clone`,   { method: 'POST' }),
  export:  (id: string) => request<{ data: any }>(`/api/v2/channels/${id}/export`),
  trigger: (id: string, body: { content_mode?: string; topic_hint?: string; topic_candidates?: string[]; max_cost_usd?: number } = {}) =>
    request(`/api/v2/channels/${id}/trigger`, { method: 'POST', body: JSON.stringify(body) }),
  pauseJob:  (channelId: string, contentId: string) =>
    request(`/api/v2/channels/${channelId}/jobs/${contentId}/pause`,  { method: 'POST' }),
  resumeJob: (channelId: string, contentId: string) =>
    request(`/api/v2/channels/${channelId}/jobs/${contentId}/resume`, { method: 'POST' }),
  stopJob:   (channelId: string, contentId: string) =>
    request(`/api/v2/channels/${channelId}/jobs/${contentId}/stop`,   { method: 'POST' }),
};

// Dashboard
export const dashboardApi = {
  stats: () =>
    request<{
      data: {
        channels: { total: number; active: number; disabled: number; archived: number };
        today: { videos_total: number; delivered: number; failed: number; in_progress: number; cost: number };
        budget: { daily_limit: number; today_cost: number };
        environment_mode: string;
        emergency_stop: boolean;
      };
    }>('/api/v2/channels/stats'),
  activeJobs: (limit = 30) => {
    const q = new URLSearchParams({ limit: String(limit) });
    return request<{ data: { groups: { label: string; items: any[] }[]; next_cursor: string | null } }>(
      `/api/v2/content?${q}`
    );
  },
};

// Providers
export const providersApi = {
  categories: () => request<{ data: any[] }>('/api/v2/providers/categories'),
  credentials: (category?: string) =>
    request<{ data: any[] }>(`/api/v2/providers/credentials${category ? `?category=${category}` : ''}`),
  createCredential: (body: any) =>
    request<{ id: number; vault_path: string; backend: string }>(
      '/api/v2/providers/credentials',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  updateCredential: (id: number, body: any) =>
    request(`/api/v2/providers/credentials/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteCredential: (id: number) =>
    request(`/api/v2/providers/credentials/${id}`, { method: 'DELETE' }),
  testCredential: (id: number) =>
    request<{ data: { ok: boolean; latency_ms: number; error: string | null } }>(
      `/api/v2/providers/credentials/${id}/test`,
      { method: 'POST' }
    ),
  rotateCredential: (id: number, secret_value: string, secret_key = 'api_key', hint?: string) =>
    request(`/api/v2/providers/credentials/${id}/rotate`, {
      method: 'POST',
      body: JSON.stringify({ secret_value, secret_key, hint }),
    }),
  createCredentialFromWizard: (body: {
    category: string; provider_key: string; label: string;
    wizard_fields: Record<string, string | boolean>;
    model?: string | null; channel_id?: string | null;
    content_mode?: string | null;
  }) =>
    request<{ id: number; label: string; vault_path: string }>(
      '/api/v2/providers/credentials/from-wizard',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  setupChecklist: () =>
    request<{ data: Array<{
      category: string; label: string; required: boolean;
      configured: boolean; healthy: boolean | null;
    }> }>('/api/v2/providers/setup-checklist'),
  rotationStatus: (id: number) =>
    request<{
      id: number; label: string; category: string; provider_name: string;
      rotated_at: string | null; rotation_hint: string | null;
      days_since_rotation: number | null; overdue: boolean; warn_after_days: number;
    }>(`/api/v2/providers/credentials/${id}/rotation-status`),
  allRotationStatus: (params?: { category?: string; overdue_only?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.overdue_only) q.set('overdue_only', 'true');
    return request<{ data: Array<{
      id: number; label: string; category: string; provider_name: string;
      rotated_at: string | null; rotation_hint: string | null;
      days_since_rotation: number | null; overdue: boolean; warn_after_days: number;
    }> }>(`/api/v2/providers/credentials/rotation-status${q.toString() ? '?' + q : ''}`);
  },
  chain: (category: string) => request<{ data: any[] }>(`/api/v2/providers/chains/${category}`),
  setChain: (category: string, credential_ids: number[]) =>
    request(`/api/v2/providers/chains/${category}`, {
      method: 'PUT',
      body: JSON.stringify({ credential_ids }),
    }),
  // Scope + content-mode aware chains (provider_chains_v2)
  chainsV2: (params: { scope?: string; scope_id?: string; content_mode?: string | null; category?: string }) => {
    const q = new URLSearchParams();
    if (params.scope) q.set('scope', params.scope);
    if (params.scope_id) q.set('scope_id', params.scope_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    if (params.category) q.set('category', params.category);
    return request<{ data: any[] }>(`/api/v2/providers/chains?${q}`);
  },
  upsertChainV2: (body: { scope: string; scope_id?: string | null; content_mode?: string | null; category: string; credential_ids: number[] }) =>
    request(`/api/v2/providers/chains`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteChainV2: (params: { scope: string; category: string; scope_id?: string; content_mode?: string }) => {
    const q = new URLSearchParams({ scope: params.scope, category: params.category });
    if (params.scope_id) q.set('scope_id', params.scope_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    return request(`/api/v2/providers/chains?${q}`, { method: 'DELETE' });
  },
  resolved: (params: { category: string; channel_id?: string; content_mode?: string }) => {
    const q = new URLSearchParams({ category: params.category });
    if (params.channel_id) q.set('channel_id', params.channel_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    return request<{ data: any[]; category: string; channel_id: string | null; content_mode: string | null }>(
      `/api/v2/providers/resolved?${q}`
    );
  },
  contentModes: () =>
    request<{ data: { name: string; label: string; description: string | null; sort_order: number; is_system: boolean }[] }>(
      '/api/v2/providers/content-modes'
    ),
  healthStreamUrl: (category?: string) => {
    const q = new URLSearchParams();
    if (category) q.set('category', category);
    return `/api/v2/providers/health-stream?${q}`;
  },
  registeredProviders: (category: string) =>
    request<{ data: {
      provider_name: string;
      display_name: string;
      logo_url: string | null;
      website_url: string | null;
      has_free_tier: boolean | null;
      default_model: string | null;
      supported_models: string[];
      config_schema: Array<{
        name: string; type: string; label: string; required: boolean;
        hint?: string; placeholder?: string; options?: string[];
      }>;
      docs_url: string | null;
      pricing_tier: string | null;
    }[] }>(
      `/api/v2/providers/registered?category=${encodeURIComponent(category)}`
    ),
  supportedModels: (category: string, provider_name: string) => {
    const q = new URLSearchParams({ category, provider_name });
    return request<{ data: string[]; default?: string | null; registered: boolean; error?: string }>(
      `/api/v2/providers/models?${q}`
    );
  },
  setDefaultFallback: (id: number) =>
    request(`/api/v2/providers/credentials/${id}/default-fallback`, { method: 'PUT' }),
  clearDefaultFallback: (id: number) =>
    request(`/api/v2/providers/credentials/${id}/default-fallback`, { method: 'DELETE' }),
  setCredentialEnabled: (id: number, enabled: boolean) =>
    request<{ status: string; enabled: boolean }>(
      `/api/v2/providers/credentials/${id}/enabled`,
      { method: 'PUT', body: JSON.stringify({ enabled }) }
    ),
  setChainEntryEnabled: (chainEntryId: number, enabled: boolean) =>
    request<{ status: string; enabled: boolean }>(
      `/api/v2/providers/chains/entry/${chainEntryId}/enabled`,
      { method: 'PUT', body: JSON.stringify({ enabled }) }
    ),
  cleanSlate: () =>
    request<{ status: string; data: { tables: string[]; secrets_deleted: number } }>(
      '/api/v2/providers/_admin/clean-slate',
      { method: 'POST' }
    ),
  health: (id: number, limit = 50) =>
    request<{ data: any[] }>(`/api/v2/providers/health/${id}?limit=${limit}`),
  // Wave 2
  marketplace: () => request<{ data: any[] }>('/api/v2/providers/marketplace'),
  probeAll: () =>
    request<{ data: any[]; summary: { total: number; ok: number } }>(
      '/api/v2/providers/health/probe-all', { method: 'POST' }
    ),
  routes: (scope = 'workspace', scope_id?: string) => {
    const q = new URLSearchParams({ scope });
    if (scope_id) q.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/providers/routes?${q}`);
  },
  upsertRoute: (category: string, body: {
    policy: string; scope?: string; scope_id?: string;
    primary_credential_id?: number | null; fallback_chain?: number[]; custom_rules?: object;
  }) =>
    request<{ id: number }>(`/api/v2/providers/routes/${category}`, {
      method: 'PUT', body: JSON.stringify({ scope: 'workspace', fallback_chain: [], ...body }),
    }),
  quotas: (scope = 'workspace', scope_id?: string) => {
    const q = new URLSearchParams({ scope });
    if (scope_id) q.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/providers/quotas?${q}`);
  },
  createQuota: (body: {
    monthly_cap_usd: number; alert_pct?: number; hard_limit?: boolean;
    scope?: string; scope_id?: string; category?: string;
  }) =>
    request<{ id: number }>('/api/v2/providers/quotas', { method: 'POST', body: JSON.stringify(body) }),
  updateQuota: (id: number, body: { monthly_cap_usd: number; alert_pct?: number; hard_limit?: boolean }) =>
    request(`/api/v2/providers/quotas/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  sandboxRun: (body: {
    credential_id: number; capability: string;
    prompt?: string; text?: string; input_payload?: object;
  }) =>
    request<{ status: string; data: { run_id: number; ok: boolean; latency_ms: number; cost_usd: number | null; output: any; error: string | null } }>(
      '/api/v2/providers/sandbox/run', { method: 'POST', body: JSON.stringify(body) }
    ),
  sandboxRuns: (credential_id?: number, limit = 20) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (credential_id) q.set('credential_id', String(credential_id));
    return request<{ data: any[] }>(`/api/v2/providers/sandbox/runs?${q}`);
  },
};

// Content
export const contentApi = {
  list: (params: {
    channel_id?: string; group?: 'day' | 'week' | 'month' | 'quarter' | 'year';
    status?: string; review_state?: string; content_mode?: string;
    cursor?: string; limit?: number;
  }) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && q.set(k, String(v)));
    return request<{ data: { groups: { label: string; items: any[] }[]; group_kind: string; next_cursor: string | null } }>(
      `/api/v2/content?${q}`
    );
  },
  search: (q: string, channel_id?: string, limit = 40) => {
    const p = new URLSearchParams({ q, limit: String(limit) });
    if (channel_id) p.set('channel_id', channel_id);
    return request<{ data: any[] }>(`/api/v2/content/search?${p}`);
  },
  bulk: (action: string, ids: string[], note?: string) =>
    request<{ affected: number }>('/api/v2/content/bulk', {
      method: 'POST',
      body: JSON.stringify({ action, ids, note }),
    }),
  calendar: (start: string, end: string, channel_id?: string) => {
    const q = new URLSearchParams({ start, end });
    if (channel_id) q.set('channel_id', channel_id);
    return request<{ data: Record<string, any[]>; start: string; end: string }>(
      `/api/v2/content/calendar?${q}`
    );
  },
  // Wave 4
  detail: (contentId: string) =>
    request<{ data: any }>(`/api/v2/content/${encodeURIComponent(contentId)}`),
  stats: (channel_id?: string, period: 'day' | 'week' | 'month' = 'week') => {
    const q = new URLSearchParams({ period });
    if (channel_id) q.set('channel_id', channel_id);
    return request<{ data: { buckets: any[]; by_channel: any[] } }>(`/api/v2/content/stats?${q}`);
  },
  trigger: (body: { channel_id: string; content_mode?: string; topic_hint?: string; scheduled_for?: string }) =>
    request<{ status: string; trigger_id: number | null; content_id: string | null }>(
      '/api/v2/content/trigger', { method: 'POST', body: JSON.stringify(body) }
    ),
  triggerHistory: (channel_id?: string, limit = 20) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (channel_id) q.set('channel_id', channel_id);
    return request<{ data: any[] }>(`/api/v2/content/triggers/history?${q}`);
  },
};

// Experiments (A/B testing)
export const experimentsApi = {
  list:     (status = '')         => request<{ data: any[] }>(`/api/v2/experiments?status=${status}`),
  create:   (body: any)           => request<{ data: any }>('/api/v2/experiments', { method: 'POST', body: JSON.stringify(body) }),
  activate: (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/activate`, { method: 'POST' }),
  pause:    (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/pause`,    { method: 'POST' }),
  complete: (name: string, w='')  => request(`/api/v2/experiments/${encodeURIComponent(name)}/complete?winner=${encodeURIComponent(w)}`, { method: 'POST' }),
  results:  (name: string)        => request<{ data: any }>(`/api/v2/experiments/${encodeURIComponent(name)}/results`),
};

// Library (assets / brand / music)
export const libraryApi = {
  assets: (params: { q?: string; provider?: string; limit?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && p.set(k, String(v)));
    return request<{ data: any[] }>(`/api/v2/library/assets?${p}`);
  },
  brand:  (channel_id?: string) =>
    request<{ data: any[] }>(`/api/v2/library/brand${channel_id ? `?channel_id=${channel_id}` : ''}`),
  music:  () => request<{ data: any[] }>(`/api/v2/library/music`),
};

// DAM (Wave 3 scoped asset store)
export const damApi = {
  list: (params: {
    scope?: string; scope_id?: string; kind?: string;
    q?: string; tag?: string; origin?: string; limit?: number; offset?: number;
  } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && p.set(k, String(v)));
    return request<{ data: any[] }>(`/api/v2/library/dam/assets?${p}`);
  },
  preflight: (sha256: string) =>
    request<{ exists: boolean; asset?: any }>(`/api/v2/library/dam/assets/preflight?sha256=${sha256}`, { method: 'POST' }),
  get: (id: number) =>
    request<{ data: any }>(`/api/v2/library/dam/assets/${id}`),
  patch: (id: number, body: { display_name?: string; tags?: string[]; license?: string; expires_at?: string }) =>
    request(`/api/v2/library/dam/assets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (id: number) =>
    request(`/api/v2/library/dam/assets/${id}`, { method: 'DELETE' }),

  tags: (scope = 'workspace', scope_id?: string) => {
    const p = new URLSearchParams({ scope });
    if (scope_id) p.set('scope_id', scope_id);
    return request<{ data: string[] }>(`/api/v2/library/dam/tags?${p}`);
  },

  search: (body: { q: string; scope?: string; scope_id?: string; kind?: string; tags?: string[]; limit?: number }) =>
    request<{ data: any[]; count: number }>('/api/v2/library/dam/search', { method: 'POST', body: JSON.stringify(body) }),

  collections: (scope = 'workspace', scope_id?: string) => {
    const p = new URLSearchParams({ scope });
    if (scope_id) p.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/library/dam/collections?${p}`);
  },
  createCollection: (body: { name: string; description?: string; kind?: string; query?: object; asset_ids?: number[]; scope?: string; scope_id?: string }) =>
    request<{ id: number }>('/api/v2/library/dam/collections', { method: 'POST', body: JSON.stringify(body) }),
  updateCollection: (id: number, body: any) =>
    request(`/api/v2/library/dam/collections/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteCollection: (id: number) =>
    request(`/api/v2/library/dam/collections/${id}`, { method: 'DELETE' }),

  brandKits: (scope = 'brand', scope_id?: string) => {
    const p = new URLSearchParams({ scope });
    if (scope_id) p.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/library/dam/brand-kits?${p}`);
  },
  createBrandKit: (body: { name: string; scope?: string; scope_id?: string; palette?: object; notes?: string }) =>
    request<{ id: number }>('/api/v2/library/dam/brand-kits', { method: 'POST', body: JSON.stringify(body) }),
  updateBrandKit: (id: number, body: any) =>
    request(`/api/v2/library/dam/brand-kits/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};

// Review
export const reviewApi = {
  queue: (state = 'pending', channel_id?: string, limit = 100) => {
    const q = new URLSearchParams({ state, limit: String(limit) });
    if (channel_id) q.set('channel_id', channel_id);
    return request<{ data: any[] }>(`/api/v2/review/queue?${q}`);
  },
  get: (video_id: string) => request<{ data: any }>(`/api/v2/review/${video_id}`),
  open: (video_id: string) => request(`/api/v2/review/${video_id}/open`, { method: 'POST' }),
  decide: (video_id: string, decision: string, summary?: string) =>
    request(`/api/v2/review/${video_id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, summary }),
    }),
  editScript: (video_id: string, body: any) =>
    request(`/api/v2/review/${video_id}/script/edit`, { method: 'POST', body: JSON.stringify(body) }),
  regenThumb: (video_id: string, prompt_nudge?: string) =>
    request(`/api/v2/review/${video_id}/thumbnail/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ prompt_nudge, keep_current: true }),
    }),
  comment: (video_id: string, body: any) =>
    request(`/api/v2/review/${video_id}/comments`, { method: 'POST', body: JSON.stringify(body) }),
  updateTitle: (video_id: string, body: { title?: string; hook?: string; topic?: string }) =>
    request(`/api/v2/review/${video_id}/title`, { method: 'PUT', body: JSON.stringify(body) }),
};

// Notifications
export const notifyApi = {
  list: (unread_only = false, severity?: string, limit = 100) => {
    const q = new URLSearchParams({ unread_only: String(unread_only), limit: String(limit) });
    if (severity) q.set('severity', severity);
    return request<{ data: any[] }>(`/api/v2/notifications?${q}`);
  },
  read: (id: number) => request(`/api/v2/notifications/${id}/read`, { method: 'POST' }),
  routes: () => request<{ data: any[] }>('/api/v2/notifications/routes'),
  upsertRoute: (body: any) => request('/api/v2/notifications/routes', { method: 'POST', body: JSON.stringify(body) }),
  updateRoute: (id: number, body: any) => request(`/api/v2/notifications/routes/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRoute: (id: number) => request(`/api/v2/notifications/routes/${id}`, { method: 'DELETE' }),
  deliveries: (notification_id?: number, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (notification_id) q.set('notification_id', String(notification_id));
    return request<{ data: any[] }>(`/api/v2/notifications/deliveries?${q}`);
  },
};

// Users
export const usersApi = {
  list: () => request<{ data: any[] }>('/api/v2/users'),
  transferSuperadmin: (targetId: number) =>
    request(`/api/v2/users/transfer-superadmin/${targetId}`, { method: 'POST' }),
  disable: (id: number) => request(`/api/v2/users/${id}/disable`, { method: 'PUT' }),
  enable: (id: number) => request(`/api/v2/users/${id}/enable`, { method: 'PUT' }),
  delete: (id: number) => request(`/api/v2/users/${id}`, { method: 'DELETE' }),
};

// Workspace
export const workspaceApi = {
  get: () => request<{ data: any }>('/api/v2/workspace'),
  update: (body: any) => request('/api/v2/workspace', { method: 'PUT', body: JSON.stringify(body) }),
  setMode: (mode: 'solo' | 'teams') => request('/api/v2/workspace', { method: 'PUT', body: JSON.stringify({ mode }) }),
  getIntegrations: () =>
    request<{ data: { slack_webhook_url: string | null } }>('/api/v2/workspace/integrations'),
  updateIntegrations: (body: { slack_webhook_url?: string | null }) =>
    request('/api/v2/workspace/integrations', { method: 'PUT', body: JSON.stringify(body) }),
};

// Entity settings
export const settingsApi = {
  get: (scope: string, scope_id: string) =>
    request<{ data: Array<{ key: string; value: any; locked: boolean }> }>(
      `/api/v2/workspace/settings?scope=${encodeURIComponent(scope)}&scope_id=${encodeURIComponent(scope_id)}`
    ),
  set: (scope: string, scope_id: string, key: string, value: any, locked = false) =>
    request('/api/v2/workspace/settings', {
      method: 'PUT',
      body: JSON.stringify({ scope, scope_id, key, value, locked }),
    }),
};

// Brands
export const brandsApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/brands'),
  get: (id: number) => request<{ data: any }>(`/api/v2/workspace/brands/${id}`),
  create: (body: any) => request<{ id: number }>('/api/v2/workspace/brands', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: any) => request(`/api/v2/workspace/brands/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};

// Series
export const seriesApi = {
  list: (channel_id?: string) =>
    request<{ data: any[] }>(`/api/v2/workspace/series${channel_id ? `?channel_id=${channel_id}` : ''}`),
  create: (body: any) => request<{ id: number }>('/api/v2/workspace/series', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: any) => request(`/api/v2/workspace/series/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: number) => request(`/api/v2/workspace/series/${id}`, { method: 'DELETE' }),
};

// Campaigns
export const campaignsApi = {
  list: (brand_id?: number, status?: string) => {
    const p = new URLSearchParams();
    if (brand_id) p.set('brand_id', String(brand_id));
    if (status) p.set('status', status);
    return request<{ data: any[] }>(`/api/v2/workspace/campaigns?${p}`);
  },
  create: (body: any) => request<{ id: number }>('/api/v2/workspace/campaigns', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: any) => request(`/api/v2/workspace/campaigns/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};

// Projects
export const projectsApi = {
  list: (params: { channel_id?: string; status?: string; series_id?: number; campaign_id?: number; limit?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && p.set(k, String(v)));
    return request<{ data: any[] }>(`/api/v2/workspace/projects?${p}`);
  },
  get: (id: number) => request<{ data: any }>(`/api/v2/workspace/projects/${id}`),
  create: (body: any) => request<{ id: number }>('/api/v2/workspace/projects', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: any) => request(`/api/v2/workspace/projects/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: number) => request(`/api/v2/workspace/projects/${id}`, { method: 'DELETE' }),
};

// Members
export const membersApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/members'),
  setRole: (user_id: number, role: string) =>
    request(`/api/v2/workspace/members/${user_id}/role`, { method: 'PUT', body: JSON.stringify({ role }) }),
  remove: (user_id: number) => request(`/api/v2/workspace/members/${user_id}`, { method: 'DELETE' }),
};

// Invites
export const invitesApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/invites'),
  create: (email: string, role: string, expires_days = 7) =>
    request<{ status: string; id: number; token: string; invite_url: string }>(
      '/api/v2/workspace/invites',
      { method: 'POST', body: JSON.stringify({ email, role, expires_days }) }
    ),
  revoke: (id: number) => request(`/api/v2/workspace/invites/${id}`, { method: 'DELETE' }),
};

// Jobs (Wave 6)
export const jobsApi = {
  active: () => request<{ status: string; data: any[] }>('/api/v2/jobs/active'),
  progress: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/progress`),
  output: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/output`),
  metadata: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/metadata`),
  approve: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  reject: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/reject`, { method: 'POST' }),
  retry: (id: string) => request<{ status: string; data?: { new_content_id?: string } }>(`/api/v2/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  restart: (id: string) => request<{ status: string; data?: { resume_from?: string } }>(`/api/v2/jobs/${encodeURIComponent(id)}/restart`, { method: 'POST' }),
  pause: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/pause`, { method: 'POST' }),
  resume: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' }),
  stop: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
};

// Session utilities
export function isLoggedIn(): boolean {
  if (typeof window === 'undefined') return false;
  // v2 JWT: check non-HttpOnly auth_status cookie set by the backend on login
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

// Legacy password-only login (used when auth.v2.enabled = FALSE).
export async function legacyLogin(password: string): Promise<void> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  setToken(data.token, data.expires_in);
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

// System (Wave 6)
export const systemApi = {
  config: () => request<{ status: string; data: { key: string; value: string; description: string }[] }>('/api/v2/system/config'),
  updateConfig: (config_key: string, config_value: string) =>
    request('/api/v2/system/config', { method: 'PUT', body: JSON.stringify({ config_key, config_value }) }),
  emergencyStop: () => request('/api/v2/system/emergency-stop', { method: 'POST' }),
  emergencyResume: () => request('/api/v2/system/emergency-resume', { method: 'POST' }),
  fleetHealth: () => request<{ status: string; data: any }>('/api/v2/system/fleet-health'),
  environment: () => request<{ status: string; data: any }>('/api/v2/system/environment'),
  cleanSlate: () => request('/api/v2/system/clean-slate', { method: 'POST' }),
};

export type ChangeRequestType =
  | 'add_credential'
  | 'change_chain_priority'
  | 'remove_credential'
  | 'change_model'
  | 'rotate_credential';

export type ChangeRequestStatus =
  | 'pending_admin'
  | 'pending_owner'
  | 'applied'
  | 'rejected_by_admin'
  | 'rejected_by_owner'
  | 'expired';

export interface ChangeRequest {
  id: number;
  workspace_id: number;
  requested_by: number;
  requester_name: string | null;
  requester_email: string | null;
  requested_at: string;
  request_type: ChangeRequestType;
  category: string;
  provider_name: string | null;
  payload: Record<string, unknown>;
  reason: string;
  status: ChangeRequestStatus;
  admin_reviewed_by: number | null;
  admin_reviewer_name: string | null;
  admin_reviewed_at: string | null;
  admin_note: string | null;
  owner_reviewed_by: number | null;
  owner_reviewer_name: string | null;
  owner_reviewed_at: string | null;
  owner_note: string | null;
  applied_at: string | null;
  expires_at: string;
  created_at: string;
}

export const changeRequestsApi = {
  list: (params?: { status?: string; category?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.category) q.set('category', params.category);
    return request<{ status: string; data: ChangeRequest[] }>(`/api/v2/providers/change-requests?${q}`);
  },
  create: (body: {
    request_type: ChangeRequestType;
    category: string;
    provider_name?: string;
    payload?: Record<string, unknown>;
    reason: string;
  }) =>
    request<{ status: string; data: { id: number } }>('/api/v2/providers/change-requests', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  get: (id: number) =>
    request<{ status: string; data: ChangeRequest }>(`/api/v2/providers/change-requests/${id}`),
  adminReview: (id: number, action: 'approve_forward' | 'reject', note?: string) =>
    request<{ status: string; data: { new_status: string } }>(
      `/api/v2/providers/change-requests/${id}/admin-review`,
      { method: 'POST', body: JSON.stringify({ action, note }) },
    ),
  ownerReview: (id: number, action: 'approve' | 'reject', note?: string) =>
    request<{ status: string; data: { new_status: string } }>(
      `/api/v2/providers/change-requests/${id}/owner-review`,
      { method: 'POST', body: JSON.stringify({ action, note }) },
    ),
};

export interface YouTubeOAuthStatus {
  connected: boolean;
  channel_name?: string | null;
  channel_avatar?: string | null;
  channel_id?: string | null;
  connected_at?: string | null;
  missing_scopes?: string[];
}

export const youtubeOAuthApi = {
  authUrl: () => '/api/v2/providers/youtube/auth',
  status: () =>
    request<{ status: string; data: YouTubeOAuthStatus }>('/api/v2/providers/youtube/status'),
  disconnect: () =>
    request('/api/v2/providers/youtube/disconnect', { method: 'DELETE' }),
};
