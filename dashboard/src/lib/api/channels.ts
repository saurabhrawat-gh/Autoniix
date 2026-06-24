import { request } from './client';

export const channelsApi = {
  list: (includeArchived = false) =>
    request<{ data: any[] }>(`/api/v2/channels?include_archived=${includeArchived}`),
  get: (id: string) => request<{ data: any }>(`/api/v2/channels/${id}`),
  create: (body: unknown) => request<{ channel_id: string }>('/api/v2/channels', { method: 'POST', body: JSON.stringify(body) }),
  patch: (id: string, body: unknown) => request(`/api/v2/channels/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  upsertProfile: (id: string, payload: unknown) =>
    request(`/api/v2/channels/${id}/profile`, { method: 'PUT', body: JSON.stringify({ payload }) }),
  presets: () => request<{ data: any[] }>('/api/v2/channels/presets'),
  addPillar: (id: string, body: unknown) => request(`/api/v2/channels/${id}/pillars`, { method: 'POST', body: JSON.stringify(body) }),
  deletePillar: (id: string, pid: number) => request(`/api/v2/channels/${id}/pillars/${pid}`, { method: 'DELETE' }),
  addRule: (id: string, body: unknown) => request(`/api/v2/channels/${id}/topic-rules`, { method: 'POST', body: JSON.stringify(body) }),
  deleteRule: (id: string, rid: number) => request(`/api/v2/channels/${id}/topic-rules/${rid}`, { method: 'DELETE' }),
  addReference: (id: string, body: unknown) => request(`/api/v2/channels/${id}/references`, { method: 'POST', body: JSON.stringify(body) }),
  deleteReference: (id: string, rid: number) => request(`/api/v2/channels/${id}/references/${rid}`, { method: 'DELETE' }),
  fieldSuggest: (field: string, context: unknown = {}) =>
    request<{ data: { suggestion: string; rationale: string } }>(
      '/api/v2/channels/ai/field-suggest',
      { method: 'POST', body: JSON.stringify({ field, context }) }
    ),
  draftCreate: (current_step: number, payload: unknown) =>
    request<{ id: number }>('/api/v2/channels/drafts', { method: 'POST', body: JSON.stringify({ current_step, payload }) }),
  draftSave: (id: number, current_step: number, payload: unknown) =>
    request(`/api/v2/channels/drafts/${id}`, { method: 'PUT', body: JSON.stringify({ current_step, payload }) }),
  draftGet: (id: number) => request<{ data: any }>(`/api/v2/channels/drafts/${id}`),
  enable:  (id: string) => request(`/api/v2/channels/${id}/enable`,  { method: 'PUT' }),
  disable: (id: string) => request(`/api/v2/channels/${id}/disable`, { method: 'PUT' }),
  archive: (id: string) => request(`/api/v2/channels/${id}/archive`, { method: 'PUT' }),
  restore: (id: string) => request(`/api/v2/channels/${id}/restore`, { method: 'PUT' }),
  delete:  (id: string, body: { confirmation: 'delete'; password: string }) =>
    request<{ status: string; data: { deleted: boolean; channel_id: string } }>(
      `/api/v2/channels/${id}`, { method: 'DELETE', body: JSON.stringify(body) }
    ),
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
