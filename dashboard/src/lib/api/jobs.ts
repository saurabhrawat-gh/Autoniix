import { request } from './client';

export const jobsApi = {
  active: () => request<{ status: string; data: any[] }>('/api/v2/jobs/active'),
  progress: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/progress`),
  output: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/output`),
  metadata: (id: string) => request<{ status: string; data: any }>(`/api/v2/jobs/${encodeURIComponent(id)}/metadata`),
  approve: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  reject: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/reject`, { method: 'POST' }),
  retry: (id: string) => request<{ status: string; data?: { new_content_id?: string } }>(`/api/v2/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  restart: (id: string) => request<{ status: string; data?: { resume_from?: string } }>(`/api/v2/jobs/${encodeURIComponent(id)}/restart`, { method: 'POST' }),
  pause: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/pause`, { method: 'POST' }),
  resume: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' }),
  stop: (id: string) => request(`/api/v2/jobs/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
};
