import { request } from './client';

export type DashboardStats = {
  channels: { total: number; active: number; disabled: number; archived: number };
  today: { videos_total: number; delivered: number; failed: number; in_progress: number; cost: number };
  budget: { daily_limit: number; today_cost: number };
  environment_mode: string;
  emergency_stop: boolean;
};

export const dashboardApi = {
  stats: () => request<{ data: DashboardStats }>('/api/v2/channels/stats'),
  activeJobs: (limit = 30) => {
    const q = new URLSearchParams({ limit: String(limit) });
    return request<{ data: { groups: { label: string; items: unknown[] }[]; next_cursor: string | null } }>(
      `/api/v2/content?${q}`
    );
  },
};
