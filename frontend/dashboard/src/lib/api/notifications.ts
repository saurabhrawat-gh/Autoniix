import { request } from './client';

export const notifyApi = {
  list: (unread_only = false, severity?: string, limit = 100) => {
    const q = new URLSearchParams({ unread_only: String(unread_only), limit: String(limit) });
    if (severity) q.set('severity', severity);
    return request<{ data: any[] }>(`/api/v2/notifications?${q}`);
  },
  read: (id: number) => request(`/api/v2/notifications/${id}/read`, { method: 'POST' }),
  routes: () => request<{ data: any[] }>('/api/v2/notifications/routes'),
  upsertRoute: (body: unknown) => request('/api/v2/notifications/routes', { method: 'POST', body: JSON.stringify(body) }),
  updateRoute: (id: number, body: unknown) => request(`/api/v2/notifications/routes/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRoute: (id: number) => request(`/api/v2/notifications/routes/${id}`, { method: 'DELETE' }),
  deliveries: (notification_id?: number, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (notification_id) q.set('notification_id', String(notification_id));
    return request<{ data: any[] }>(`/api/v2/notifications/deliveries?${q}`);
  },
};
