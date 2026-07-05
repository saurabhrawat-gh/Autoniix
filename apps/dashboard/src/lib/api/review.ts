import { request } from './client';

export type ReviewProfile = 'hands_off' | 'quick' | 'standard' | 'full_control' | 'custom';

export interface ReviewGates {
  research_data: boolean;
  brand_alignment_report: boolean;
  topic_title: boolean;
  story_script: boolean;
  script_voice_data: boolean;
  script_assets_data: boolean;
  script_direction_data: boolean;
  voice_track: boolean;
  scene_images: boolean;
  remotion_v3_json: boolean;
  metadata: boolean;
  thumbnail: boolean;
  final_video: boolean;
}

export interface ReviewConfig {
  channel_id: string;
  profile: ReviewProfile;
  gates: ReviewGates;
}

export interface ReviewConfigUpdate {
  profile: ReviewProfile;
  gates?: Partial<ReviewGates>;
}

export const reviewApi = {
  queue: (state = 'pending', channel_id?: string, limit = 100) => {
    const q = new URLSearchParams({ state, limit: String(limit) });
    if (channel_id) q.set('channel_id', channel_id);
    return request<{ data: unknown[] }>(`/api/v2/review/queue?${q}`);
  },
  get: (video_id: string) => request<{ data: unknown }>(`/api/v2/review/${video_id}`),
  open: (video_id: string) => request(`/api/v2/review/${video_id}/open`, { method: 'POST' }),
  decide: (video_id: string, decision: string, summary?: string) =>
    request(`/api/v2/review/${video_id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, summary }),
    }),
  editScript: (video_id: string, body: unknown) =>
    request(`/api/v2/review/${video_id}/script/edit`, { method: 'POST', body: JSON.stringify(body) }),
  regenThumb: (video_id: string, prompt_nudge?: string) =>
    request(`/api/v2/review/${video_id}/thumbnail/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ prompt_nudge, keep_current: true }),
    }),
  comment: (video_id: string, body: unknown) =>
    request(`/api/v2/review/${video_id}/comments`, { method: 'POST', body: JSON.stringify(body) }),
  updateTitle: (video_id: string, body: { title?: string; hook?: string; topic?: string }) =>
    request(`/api/v2/review/${video_id}/title`, { method: 'PUT', body: JSON.stringify(body) }),
};

export const reviewConfigApi = {
  get: (channelId: string) =>
    request<ReviewConfig>(`/api/v2/channels/${encodeURIComponent(channelId)}/settings/review`),
  update: (channelId: string, body: ReviewConfigUpdate) =>
    request<ReviewConfig>(`/api/v2/channels/${encodeURIComponent(channelId)}/settings/review`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
};
