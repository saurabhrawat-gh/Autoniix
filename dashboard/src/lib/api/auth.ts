import { request, clearToken, BASE } from './client';
import type { components } from './types';

export type RegisterResponse = components['schemas']['RegisterResponse'];
export type SignInResponse = components['schemas']['SignInResponse'];
export type UserResponse = components['schemas']['UserResponse'];
export type CurrentUserResponse = components['schemas']['CurrentUserResponse'];

export type MeResponse = {
  data: {
    user_id: number | null;
    email: string | null;
    role: string;
    global_role: string;
    workspace_id: number;
    source: string;
    display_name: string | null;
    initials: string;
    permissions: string[];
  };
};

export type WorkspaceListItem = {
  id: number;
  name: string;
  slug: string;
  plan: string;
  role: string;
  active: boolean;
  onboarding_completed: boolean;
};

export const authApi = {
  mode: () =>
    fetch(`${BASE}/api/v2/auth/mode`).then(r => r.json()) as Promise<{ v2_enabled: boolean; legacy_enabled: boolean }>,
  register: (email: string, password: string, workspace_name: string, display_name?: string) =>
    request<RegisterResponse>('/api/v2/auth/register', { method: 'POST', body: JSON.stringify({ email, password, workspace_name, display_name }) }),
  login: async (email: string, password: string, mfa_code?: string) => {
    // Use raw fetch — NOT the request() wrapper — so a 401 from the login
    // endpoint is surfaced as an error to the caller instead of triggering
    // the global refresh-then-redirect interceptor.
    const res = await fetch(`${BASE}/api/v2/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Source': 'ui' },
      body: JSON.stringify({ email, password, mfa_code }),
      credentials: 'include',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as Record<string, unknown>;
      throw new Error((body.detail as string) || (body.error as string) || `HTTP ${res.status}`);
    }
    return res.json() as Promise<SignInResponse>;
  },
  refresh: async (): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/api/v2/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as Record<string, unknown>;
      throw new Error((body.detail as string) || (body.error as string) || `HTTP ${res.status}`);
    }
    return res.json();
  },
  logout: async () => {
    clearToken();
    return request('/api/v2/auth/logout', { method: 'POST' });
  },
  me: () => request<MeResponse>('/api/v2/auth/me'),
  forgot: (email: string) =>
    request<{ reset_token?: string }>('/api/v2/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
  reset: (token: string, password: string) =>
    request('/api/v2/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) }),
  mfaSetup: () => request<{ data: { otpauth_url: string; secret: string } }>('/api/v2/auth/mfa/setup', { method: 'POST' }),
  mfaVerify: (code: string) =>
    request('/api/v2/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
  updateProfile: (data: { display_name?: string; current_password?: string; new_password?: string }) =>
    request<{ status: string; message: string }>('/api/v2/auth/profile', { method: 'PUT', body: JSON.stringify(data) }),
  deleteAccount: (password: string) =>
    request<{ status: string }>('/api/v2/auth/account', { method: 'DELETE', body: JSON.stringify({ password }) }),
  listWorkspaces: () =>
    request<{ data: WorkspaceListItem[] }>('/api/v2/auth/workspaces'),
  switchWorkspace: (workspace_id: number) =>
    request<{ status: string; workspace_id: number; role: string }>(
      '/api/v2/auth/switch-workspace',
      { method: 'POST', body: JSON.stringify({ workspace_id }) }
    ),
  acceptInvite: (token: string, password?: string, display_name?: string) =>
    request<{ status: string; workspace_id: number; role: string }>(
      '/api/v2/auth/accept-invite',
      { method: 'POST', body: JSON.stringify({ token, password, display_name }) }
    ),
  createWorkspace: (workspace_name: string) =>
    request<{ status: string; workspace_id: number; role: string; access_token: string }>(
      '/api/v2/auth/create-workspace',
      { method: 'POST', body: JSON.stringify({ workspace_name }) }
    ),
  listSessions: () =>
    request<{ data: Array<{ id: number; ip: string | null; user_agent: string | null; created_at: string; last_seen_at: string; expires_at: string }> }>(
      '/api/v2/me/sessions'
    ),
  revokeSession: (session_id: number) =>
    request<{ status: string }>(`/api/v2/me/sessions/${session_id}`, { method: 'DELETE' }),
};
