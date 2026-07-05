import { request } from './client';

export interface LookupValue {
  id: number;
  type: string;
  value: string;
  label: string;
  parent_value: string | null;
  workspace_id: number | null;
  sort_order: number;
  is_active: boolean;
  is_custom: boolean;
}

export interface FinishingConfig {
  channel_id: string;
  require_resolve_finish: boolean;
  color_grade_preset: string;
  audio_denoise: boolean;
  audio_eq: boolean;
  audio_compress: boolean;
  audio_music_duck: boolean;
  audio_loudness_lufs: number;
  audio_true_peak_dbtps: number;
  output_prores_archive: boolean;
  updated_at: string | null;
}

export type FinishingConfigUpdate = Partial<Omit<FinishingConfig, 'channel_id' | 'updated_at'>>;

export interface FinishingPreset {
  key: string;
  display_name: string;
  description: string;
  thumbnail_url: string;
  best_for: string[];
}

export const lookupValuesApi = {
  list: (type?: string, parent_value?: string) => {
    const q = new URLSearchParams();
    if (type) q.set('type', type);
    if (parent_value) q.set('parent_value', parent_value);
    return request<{ data: LookupValue[] }>(`/api/v2/lookup-values?${q}`);
  },
  createGlobal: (body: { type: string; value: string; label: string; parent_value?: string; sort_order?: number }) =>
    request<LookupValue>('/api/v2/lookup-values', { method: 'POST', body: JSON.stringify(body) }),
  createWorkspace: (body: { type: string; value: string; label: string; parent_value?: string; sort_order?: number }) =>
    request<LookupValue>('/api/v2/workspace/lookup-values', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: { label?: string; sort_order?: number; is_active?: boolean }) =>
    request(`/api/v2/lookup-values/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deactivate: (id: number) =>
    request(`/api/v2/lookup-values/${id}`, { method: 'DELETE' }),
};

export const resolveConfigApi = {
  get: (channelId: string, content_mode?: string) => {
    const q = content_mode ? `?content_mode=${content_mode}` : '';
    return request<{ channel_id: string; content_mode: string | null; resolved: Record<string, { value: unknown; scope: string }> }>(
      `/api/v2/channels/${encodeURIComponent(channelId)}/resolve-config${q}`
    );
  },
};

export const resolveChainApi = {
  get: (category: string, opts?: { content_mode?: string; channel_id?: string }) => {
    const q = new URLSearchParams({ category });
    if (opts?.content_mode) q.set('content_mode', opts.content_mode);
    if (opts?.channel_id) q.set('channel_id', opts.channel_id);
    return request<{ category: string; content_mode: string | null; scope_used: string | null; chain: unknown[] }>(
      `/api/v2/workspace/resolve-provider-chain?${q}`
    );
  },
};

export const finishingApi = {
  get: (channelId: string) =>
    request<FinishingConfig>(`/api/v2/channels/${encodeURIComponent(channelId)}/settings/finishing`),
  update: (channelId: string, body: FinishingConfigUpdate) =>
    request<FinishingConfig>(`/api/v2/channels/${encodeURIComponent(channelId)}/settings/finishing`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  presets: () => request<{ presets: FinishingPreset[] }>('/api/v2/finishing/presets'),
};
