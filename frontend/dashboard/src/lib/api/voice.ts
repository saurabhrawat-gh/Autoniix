import { request } from './client';

export interface ElevenLabsVoice {
  voice_id: string;
  name: string;
  category: string | null;
  preview_url: string | null;
}

export const voiceApi = {
  listVoices: () =>
    request<{ data: ElevenLabsVoice[]; warning?: string }>('/api/v2/voice/voices'),

  preview: (body: {
    voice_id: string;
    text?: string;
    stability?: number;
    similarity_boost?: number;
    style?: number;
  }) =>
    request<{ voice_id: string; data_url: string; chars: number }>(
      '/api/v2/voice/preview',
      { method: 'POST', body: JSON.stringify(body) }
    ),
};
