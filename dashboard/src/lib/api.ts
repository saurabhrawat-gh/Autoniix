const BASE = process.env.NEXT_PUBLIC_API_URL || '';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('dashboard_token');
}

export function setToken(token: string, expiresIn?: number) {
  localStorage.setItem('dashboard_token', token);
  if (expiresIn) {
    localStorage.setItem('dashboard_token_expires', String(Date.now() + expiresIn * 1000));
  }
}

export function clearToken() {
  localStorage.removeItem('dashboard_token');
  localStorage.removeItem('dashboard_token_expires');
}

export function isLoggedIn(): boolean {
  const token = getToken();
  if (!token) return false;
  const expires = localStorage.getItem('dashboard_token_expires');
  if (expires && Date.now() > parseInt(expires, 10)) {
    clearToken();
    return false;
  }
  return true;
}

async function request<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  login: (password: string) =>
    request<{ token: string; expires_in: number }>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ password }),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),

  // Stats
  stats: () => request('/api/stats'),

  // Channels
  channels: (includeArchived = false) =>
    request(`/api/channels?include_archived=${includeArchived}`),
  createChannel: (data: any) =>
    request('/api/channels', { method: 'POST', body: JSON.stringify(data) }),
  updateChannel: (id: string, data: any) =>
    request(`/api/channels/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  enableChannel: (id: string) =>
    request(`/api/channels/${id}/enable`, { method: 'PUT' }),
  disableChannel: (id: string) =>
    request(`/api/channels/${id}/disable`, { method: 'PUT' }),
  archiveChannel: (id: string) =>
    request(`/api/channels/${id}/archive`, { method: 'PUT' }),
  restoreChannel: (id: string) =>
    request(`/api/channels/${id}/restore`, { method: 'PUT' }),
  cloneChannel: (id: string) =>
    request(`/api/channels/${id}/clone`, { method: 'POST' }),
  exportChannel: (id: string) =>
    request(`/api/channels/${id}/export`),

  // Workflow control
  trigger: (id: string, data: any = {}) =>
    request(`/api/channels/${id}/trigger`, { method: 'POST', body: JSON.stringify(data) }),
  pause: (id: string) =>
    request(`/api/channels/${id}/pause`, { method: 'POST' }),
  resume: (id: string) =>
    request(`/api/channels/${id}/resume`, { method: 'POST' }),
  stop: (id: string) =>
    request(`/api/channels/${id}/stop`, { method: 'POST' }),

  // Jobs
  jobs: (channelId: string, contentMode?: string) => {
    const params = new URLSearchParams();
    if (contentMode) params.set('content_mode', contentMode);
    return request(`/api/channels/${channelId}/jobs?${params}`);
  },
  jobProgress: (contentId: string) =>
    request(`/api/jobs/${contentId}/progress`),
  jobMetadata: (contentId: string) =>
    request(`/api/jobs/${contentId}/metadata`),
  jobOutput: (contentId: string) =>
    request(`/api/jobs/${contentId}/output`),

  // Workflow status
  workflowStatus: (channelId: string) =>
    request(`/api/channels/${channelId}/workflow-status`),

  // Active jobs (all in-progress)
  activeJobs: () => request('/api/jobs/active'),

  // Job approval / rejection / retry
  approveJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/approve`, { method: 'POST' }),
  rejectJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/reject`, { method: 'POST' }),
  retryJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/retry`, { method: 'POST' }),

  // Per-job workflow control
  pauseJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/pause`, { method: 'POST' }),
  resumeJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/resume`, { method: 'POST' }),
  stopJob: (contentId: string) =>
    request(`/api/jobs/${contentId}/stop`, { method: 'POST' }),

  // Config
  config: () => request('/api/config'),
  updateConfig: (key: string, value: string) =>
    request('/api/config', { method: 'PUT', body: JSON.stringify({ config_key: key, config_value: value }) }),
  emergencyStop: () => request('/api/emergency-stop', { method: 'POST' }),
  emergencyResume: () => request('/api/emergency-resume', { method: 'POST' }),

  // Environment
  environment: () => request('/api/environment'),
  switchEnvironment: (mode: string, confirm: boolean = false) =>
    request('/api/environment', { method: 'PUT', body: JSON.stringify({ mode, confirm }) }),
  testDataStats: () => request('/api/test-data/stats'),
  cleanupTestData: () => request('/api/test-data', { method: 'DELETE' }),
};

export function wsProgress(contentId: string): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = process.env.NEXT_PUBLIC_WS_URL || `${proto}//${window.location.host}`;
  return new WebSocket(`${host}/api/ws/progress/${contentId}`);
}
