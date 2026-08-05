import { request } from './client';

export const workspaceApi = {
  get: () => request<{ data: any }>('/api/v2/workspace'),
  update: (body: unknown) => request('/api/v2/workspace', { method: 'PUT', body: JSON.stringify(body) }),
  setMode: (mode: 'solo' | 'teams') => request('/api/v2/workspace', { method: 'PUT', body: JSON.stringify({ mode }) }),
  getIntegrations: () =>
    request<{ data: { slack_webhook_url: string | null } }>('/api/v2/workspace/integrations'),
  updateIntegrations: (body: { slack_webhook_url?: string | null }) =>
    request('/api/v2/workspace/integrations', { method: 'PUT', body: JSON.stringify(body) }),
};

export const settingsApi = {
  get: (scope: string, scope_id: string) =>
    request<{ data: Array<{ key: string; value: any; locked: boolean }> }>(
      `/api/v2/workspace/settings?scope=${encodeURIComponent(scope)}&scope_id=${encodeURIComponent(scope_id)}`
    ),
  set: (scope: string, scope_id: string, key: string, value: unknown, locked = false) =>
    request('/api/v2/workspace/settings', {
      method: 'PUT',
      body: JSON.stringify({ scope, scope_id, key, value, locked }),
    }),
};

export const brandsApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/brands'),
  get: (id: number) => request<{ data: any }>(`/api/v2/workspace/brands/${id}`),
  create: (body: unknown) => request<{ id: number }>('/api/v2/workspace/brands', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: unknown) => request(`/api/v2/workspace/brands/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};

export const seriesApi = {
  list: (channel_id?: string) =>
    request<{ data: any[] }>(`/api/v2/workspace/series${channel_id ? `?channel_id=${channel_id}` : ''}`),
  create: (body: unknown) => request<{ id: number }>('/api/v2/workspace/series', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: unknown) => request(`/api/v2/workspace/series/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: number) => request(`/api/v2/workspace/series/${id}`, { method: 'DELETE' }),
};

export const campaignsApi = {
  list: (brand_id?: number, status?: string) => {
    const p = new URLSearchParams();
    if (brand_id) p.set('brand_id', String(brand_id));
    if (status) p.set('status', status);
    return request<{ data: any[] }>(`/api/v2/workspace/campaigns?${p}`);
  },
  create: (body: unknown) => request<{ id: number }>('/api/v2/workspace/campaigns', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: unknown) => request(`/api/v2/workspace/campaigns/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};

export const projectsApi = {
  list: (params: { channel_id?: string; status?: string; series_id?: number; campaign_id?: number; limit?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && p.set(k, String(v)));
    return request<{ data: any[] }>(`/api/v2/workspace/projects?${p}`);
  },
  get: (id: number) => request<{ data: any }>(`/api/v2/workspace/projects/${id}`),
  create: (body: unknown) => request<{ id: number }>('/api/v2/workspace/projects', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: unknown) => request(`/api/v2/workspace/projects/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: number) => request(`/api/v2/workspace/projects/${id}`, { method: 'DELETE' }),
};

export const membersApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/members'),
  setRole: (user_id: number, role: string) =>
    request(`/api/v2/workspace/members/${user_id}/role`, { method: 'PUT', body: JSON.stringify({ role }) }),
  remove: (user_id: number) => request(`/api/v2/workspace/members/${user_id}`, { method: 'DELETE' }),
  transferOwnership: (new_owner_user_id: number, current_password: string) =>
    request('/api/v2/workspace/transfer-ownership', {
      method: 'POST',
      body: JSON.stringify({ new_owner_user_id, current_password }),
    }),
};

export const invitesApi = {
  list: () => request<{ data: any[] }>('/api/v2/workspace/invites'),
  create: (email: string, role: string, expires_days = 7) =>
    request<{ status: string; id: number; token: string; invite_url: string }>(
      '/api/v2/workspace/invites',
      { method: 'POST', body: JSON.stringify({ email, role, expires_days }) }
    ),
  revoke: (id: number) => request(`/api/v2/workspace/invites/${id}`, { method: 'DELETE' }),
};
