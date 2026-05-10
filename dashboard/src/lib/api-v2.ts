/**
 * v2 API client.
 *
 * Authenticates with either the legacy session token (set by /api/auth/login)
 * or a v2 JWT (set by /api/v2/auth/login). The backend accepts both for v2
 * endpoints, so we just send whichever is present.
 */
const BASE = process.env.NEXT_PUBLIC_API_URL || '';

function readToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('v2_access_token') || localStorage.getItem('dashboard_token');
}

export function setV2Tokens(access: string, refresh: string) {
  localStorage.setItem('v2_access_token', access);
  localStorage.setItem('v2_refresh_token', refresh);
}

export function clearV2Tokens() {
  localStorage.removeItem('v2_access_token');
  localStorage.removeItem('v2_refresh_token');
}

async function request<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = readToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Source': 'ui',
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearV2Tokens();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Flags ─────────────────────────────────────────────────
export const flagsApi = {
  list: () => request<{ data: Array<{ key: string; enabled: boolean; description: string; payload: any }> }>('/api/v2/flags'),
  set: (key: string, enabled: boolean, payload: any = {}) =>
    request(`/api/v2/flags/${key}`, { method: 'PUT', body: JSON.stringify({ enabled, payload }) }),
};

// ── Auth ──────────────────────────────────────────────────
export const authApi = {
  register: (email: string, password: string, display_name?: string) =>
    request('/api/v2/auth/register', { method: 'POST', body: JSON.stringify({ email, password, display_name }) }),
  login: (email: string, password: string, mfa_code?: string) =>
    request<{ access_token: string; refresh_token: string; user: any }>(
      '/api/v2/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password, mfa_code }) }
    ),
  refresh: (refresh_token: string) =>
    request<{ access_token: string }>('/api/v2/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token }) }),
  logout: (refresh_token: string) =>
    request('/api/v2/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token }) }),
  me: () => request<{ data: { user_id: number | null; email: string | null; role: string; source: string } }>('/api/v2/auth/me'),
  forgot: (email: string) =>
    request<{ reset_token?: string }>('/api/v2/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
  reset: (token: string, password: string) =>
    request('/api/v2/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) }),
  mfaSetup: () => request<{ data: { otpauth_url: string; secret: string } }>('/api/v2/auth/mfa/setup', { method: 'POST' }),
  mfaVerify: (code: string) =>
    request('/api/v2/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
};

// ── Channels ──────────────────────────────────────────────
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
};

// ── Providers ─────────────────────────────────────────────
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
  rotateCredential: (id: number, secret_value: string, secret_key = 'api_key') =>
    request(`/api/v2/providers/credentials/${id}/rotate`, {
      method: 'POST',
      body: JSON.stringify({ secret_value, secret_key }),
    }),
  chain: (category: string) => request<{ data: any[] }>(`/api/v2/providers/chains/${category}`),
  setChain: (category: string, credential_ids: number[]) =>
    request(`/api/v2/providers/chains/${category}`, {
      method: 'PUT',
      body: JSON.stringify({ credential_ids }),
    }),
  health: (id: number, limit = 50) =>
    request<{ data: any[] }>(`/api/v2/providers/health/${id}?limit=${limit}`),
};

// ── Content ───────────────────────────────────────────────
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
};

// ── Experiments (A/B testing) ─────────────────────────────
export const experimentsApi = {
  list:     (status = '')         => request<{ data: any[] }>(`/api/v2/experiments?status=${status}`),
  create:   (body: any)           => request<{ data: any }>('/api/v2/experiments', { method: 'POST', body: JSON.stringify(body) }),
  activate: (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/activate`, { method: 'POST' }),
  pause:    (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/pause`,    { method: 'POST' }),
  complete: (name: string, w='')  => request(`/api/v2/experiments/${encodeURIComponent(name)}/complete?winner=${encodeURIComponent(w)}`, { method: 'POST' }),
  results:  (name: string)        => request<{ data: any }>(`/api/v2/experiments/${encodeURIComponent(name)}/results`),
};

// ── Library (assets / brand / music) ──────────────────────
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

// ── Review ────────────────────────────────────────────────
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

// ── Notifications ─────────────────────────────────────────
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

// ── Users ─────────────────────────────────────────────────
export const usersApi = {
  list: () => request<{ data: any[] }>('/api/v2/users'),
  setRole: (id: number, role: string) =>
    request(`/api/v2/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) }),
  disable: (id: number) => request(`/api/v2/users/${id}/disable`, { method: 'PUT' }),
  enable: (id: number) => request(`/api/v2/users/${id}/enable`, { method: 'PUT' }),
};
