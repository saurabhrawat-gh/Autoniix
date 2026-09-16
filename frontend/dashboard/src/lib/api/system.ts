import { request } from './client';

export type EntitySetting = { key: string; value: unknown; locked: boolean };

export const systemApi = {
  config: () => request<{ status: string; data: { key: string; value: string; description: string }[] }>('/api/v2/system/config'),
  updateConfig: (config_key: string, config_value: string) =>
    request('/api/v2/system/config', { method: 'PUT', body: JSON.stringify({ config_key, config_value }) }),
  emergencyStop: () => request('/api/v2/system/emergency-stop', { method: 'POST' }),
  emergencyResume: () => request('/api/v2/system/emergency-resume', { method: 'POST' }),
  fleetHealth: () => request<{ status: string; data: any }>('/api/v2/system/fleet-health'),
  environment: () => request<{ status: string; data: any }>('/api/v2/system/environment'),
  cleanSlate: () => request('/api/v2/system/clean-slate', { method: 'POST' }),
  getEntitySettings: () =>
    request<{ status: string; data: EntitySetting[] }>('/api/v2/system/entity-settings'),
  setEntitySetting: (key: string, value: unknown, locked = false) =>
    request('/api/v2/system/entity-settings', { method: 'PUT', body: JSON.stringify({ key, value, locked }) }),
};

export const workspaceEntitySettingsApi = {
  get: () =>
    request<{ status: string; data: EntitySetting[] }>('/api/v2/workspace/entity-settings'),
  set: (key: string, value: unknown, locked = false) =>
    request('/api/v2/workspace/entity-settings', { method: 'PUT', body: JSON.stringify({ key, value, locked }) }),
};
