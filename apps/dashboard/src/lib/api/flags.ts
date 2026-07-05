import { request } from './client';

export type Flag = { key: string; enabled: boolean; description: string; payload: unknown };

export const flagsApi = {
  list: () => request<{ data: Flag[] }>('/api/v2/flags'),
  set: (key: string, enabled: boolean, payload: unknown = {}) =>
    request(`/api/v2/flags/${key}`, { method: 'PUT', body: JSON.stringify({ enabled, payload }) }),
};
