import { request } from './client';

export const usersApi = {
  list: () => request<{ data: any[] }>('/api/v2/users'),
  transferSuperadmin: (targetId: number) =>
    request(`/api/v2/users/transfer-superadmin/${targetId}`, { method: 'POST' }),
  disable: (id: number) => request(`/api/v2/users/${id}/disable`, { method: 'PUT' }),
  enable: (id: number) => request(`/api/v2/users/${id}/enable`, { method: 'PUT' }),
  delete: (id: number) => request(`/api/v2/users/${id}`, { method: 'DELETE' }),
};
