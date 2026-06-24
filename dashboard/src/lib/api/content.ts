import { request } from './client';

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
