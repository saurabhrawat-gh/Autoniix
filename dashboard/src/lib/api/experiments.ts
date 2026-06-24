import { request } from './client';

export const experimentsApi = {
  list:     (status = '')         => request<{ data: any[] }>(`/api/v2/experiments?status=${status}`),
  create:   (body: unknown)       => request<{ data: any }>('/api/v2/experiments', { method: 'POST', body: JSON.stringify(body) }),
  activate: (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/activate`, { method: 'POST' }),
  pause:    (name: string)        => request(`/api/v2/experiments/${encodeURIComponent(name)}/pause`,    { method: 'POST' }),
  complete: (name: string, w='')  => request(`/api/v2/experiments/${encodeURIComponent(name)}/complete?winner=${encodeURIComponent(w)}`, { method: 'POST' }),
  results:  (name: string)        => request<{ data: any }>(`/api/v2/experiments/${encodeURIComponent(name)}/results`),
};
