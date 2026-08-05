import { request } from './client';

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
  updateCollection: (id: number, body: unknown) =>
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
  updateBrandKit: (id: number, body: unknown) =>
    request(`/api/v2/library/dam/brand-kits/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
};
