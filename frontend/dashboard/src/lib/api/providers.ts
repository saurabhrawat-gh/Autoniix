import { request } from './client';

export type ChangeRequestType =
  | 'add_credential'
  | 'change_chain_priority'
  | 'remove_credential'
  | 'change_model'
  | 'rotate_credential';

export type ChangeRequestStatus =
  | 'pending_admin'
  | 'pending_owner'
  | 'applied'
  | 'rejected_by_admin'
  | 'rejected_by_owner'
  | 'expired';

export interface ChangeRequest {
  id: number;
  workspace_id: number;
  requested_by: number;
  requester_name: string | null;
  requester_email: string | null;
  requested_at: string;
  request_type: ChangeRequestType;
  category: string;
  provider_name: string | null;
  payload: Record<string, unknown>;
  reason: string;
  status: ChangeRequestStatus;
  admin_reviewed_by: number | null;
  admin_reviewer_name: string | null;
  admin_reviewed_at: string | null;
  admin_note: string | null;
  owner_reviewed_by: number | null;
  owner_reviewer_name: string | null;
  owner_reviewed_at: string | null;
  owner_note: string | null;
  applied_at: string | null;
  expires_at: string;
  created_at: string;
}

export interface YouTubeOAuthStatus {
  connected: boolean;
  channel_name?: string | null;
  channel_avatar?: string | null;
  channel_id?: string | null;
  connected_at?: string | null;
  missing_scopes?: string[];
}

export const providersApi = {
  categories: () => request<{ data: any[] }>('/api/v2/providers/categories'),
  kinds: () => request<{ data: any[] }>('/api/v2/providers/kinds'),
  createKind: (body: { label: string; kind?: string; icon?: string | null; description?: string | null }) =>
    request<{ kind: string; label: string }>('/api/v2/providers/kinds', { method: 'POST', body: JSON.stringify(body) }),
  deleteKind: (kind: string) =>
    request<{ categories_removed: string[] }>(`/api/v2/providers/kinds/${encodeURIComponent(kind)}`, { method: 'DELETE' }),
  createCategory: (body: { label: string; kind: string; name?: string; description?: string | null }) =>
    request<{ name: string; label: string; kind: string }>('/api/v2/providers/categories', { method: 'POST', body: JSON.stringify(body) }),
  deleteCategory: (name: string) =>
    request(`/api/v2/providers/categories/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  updateCategory: (name: string, label: string) =>
    request(`/api/v2/providers/categories/${encodeURIComponent(name)}`, { method: 'PATCH', body: JSON.stringify({ label }) }),
  createMarketplaceProvider: (body: {
    display_name: string; kind: string; provider_key?: string; description?: string | null;
    supported_models?: string[]; has_free_tier?: boolean; cost_unit?: string | null; requires_api_key?: boolean;
  }) =>
    request<{ provider_key: string; category: string }>('/api/v2/providers/marketplace', { method: 'POST', body: JSON.stringify(body) }),
  deleteMarketplaceProvider: (provider_key: string) =>
    request(`/api/v2/providers/marketplace/${encodeURIComponent(provider_key)}`, { method: 'DELETE' }),
  catalogForCategory: (category: string) =>
    request<{ data: any[]; kind: string }>(`/api/v2/providers/catalog-for-category?category=${encodeURIComponent(category)}`),
  restoreDefaults: () =>
    request<{ status: string }>('/api/v2/providers/restore-defaults', { method: 'POST' }),
  credentials: (category?: string) =>
    request<{ data: any[] }>(`/api/v2/providers/credentials${category ? `?category=${category}` : ''}`),
  createCredential: (body: unknown) =>
    request<{ id: number; vault_path: string; backend: string }>(
      '/api/v2/providers/credentials',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  updateCredential: (id: number, body: unknown) =>
    request(`/api/v2/providers/credentials/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteCredential: (id: number) =>
    request(`/api/v2/providers/credentials/${id}`, { method: 'DELETE' }),
  testCredential: (id: number) =>
    request<{ data: { ok: boolean; latency_ms: number; error: string | null } }>(
      `/api/v2/providers/credentials/${id}/test`,
      { method: 'POST' }
    ),
  rotateCredential: (id: number, secret_value: string, secret_key = 'api_key', hint?: string) =>
    request(`/api/v2/providers/credentials/${id}/rotate`, {
      method: 'POST',
      body: JSON.stringify({ secret_value, secret_key, hint }),
    }),
  createCredentialFromWizard: (body: {
    category: string; provider_key: string; label: string;
    wizard_fields: Record<string, string | boolean>;
    model?: string | null; channel_id?: string | null;
    content_mode?: string | null;
  }) =>
    request<{ id: number; label: string; vault_path: string }>(
      '/api/v2/providers/credentials/from-wizard',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  setupChecklist: () =>
    request<{ data: Array<{
      category: string; label: string; required: boolean;
      configured: boolean; healthy: boolean | null;
    }> }>('/api/v2/providers/setup-checklist'),
  rotationStatus: (id: number) =>
    request<{
      id: number; label: string; category: string; provider_name: string;
      rotated_at: string | null; rotation_hint: string | null;
      days_since_rotation: number | null; overdue: boolean; warn_after_days: number;
    }>(`/api/v2/providers/credentials/${id}/rotation-status`),
  allRotationStatus: (params?: { category?: string; overdue_only?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.overdue_only) q.set('overdue_only', 'true');
    return request<{ data: Array<{
      id: number; label: string; category: string; provider_name: string;
      rotated_at: string | null; rotation_hint: string | null;
      days_since_rotation: number | null; overdue: boolean; warn_after_days: number;
    }> }>(`/api/v2/providers/credentials/rotation-status${q.toString() ? '?' + q : ''}`);
  },
  chain: (category: string) => request<{ data: any[] }>(`/api/v2/providers/chains/${category}`),
  setChain: (category: string, credential_ids: number[]) =>
    request(`/api/v2/providers/chains/${category}`, {
      method: 'PUT',
      body: JSON.stringify({ credential_ids }),
    }),
  chainsV2: (params: { scope?: string; scope_id?: string; content_mode?: string | null; category?: string }) => {
    const q = new URLSearchParams();
    if (params.scope) q.set('scope', params.scope);
    if (params.scope_id) q.set('scope_id', params.scope_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    if (params.category) q.set('category', params.category);
    return request<{ data: any[] }>(`/api/v2/providers/chains?${q}`);
  },
  upsertChainV2: (body: { scope: string; scope_id?: string | null; content_mode?: string | null; category: string; credential_ids: number[] }) =>
    request(`/api/v2/providers/chains`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteChainV2: (params: { scope: string; category: string; scope_id?: string; content_mode?: string }) => {
    const q = new URLSearchParams({ scope: params.scope, category: params.category });
    if (params.scope_id) q.set('scope_id', params.scope_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    return request(`/api/v2/providers/chains?${q}`, { method: 'DELETE' });
  },
  resolved: (params: { category: string; channel_id?: string; content_mode?: string }) => {
    const q = new URLSearchParams({ category: params.category });
    if (params.channel_id) q.set('channel_id', params.channel_id);
    if (params.content_mode) q.set('content_mode', params.content_mode);
    return request<{ data: any[]; category: string; channel_id: string | null; content_mode: string | null }>(
      `/api/v2/providers/resolved?${q}`
    );
  },
  contentModes: () =>
    request<{ data: { name: string; label: string; description: string | null; sort_order: number; is_system: boolean }[] }>(
      '/api/v2/providers/content-modes'
    ),
  healthStreamUrl: (category?: string) => {
    const q = new URLSearchParams();
    if (category) q.set('category', category);
    return `/api/v2/providers/health-stream?${q}`;
  },
  registeredProviders: (category: string) =>
    request<{ data: {
      provider_name: string; display_name: string; logo_url: string | null;
      website_url: string | null; has_free_tier: boolean | null; default_model: string | null;
      supported_models: string[]; config_schema: Array<{
        name: string; type: string; label: string; required: boolean;
        hint?: string; placeholder?: string; options?: string[];
      }>; docs_url: string | null; pricing_tier: string | null;
    }[] }>(
      `/api/v2/providers/registered?category=${encodeURIComponent(category)}`
    ),
  supportedModels: (category: string, provider_name: string) => {
    const q = new URLSearchParams({ category, provider_name });
    return request<{ data: string[]; default?: string | null; registered: boolean; error?: string }>(
      `/api/v2/providers/models?${q}`
    );
  },
  setDefaultFallback: (id: number) =>
    request(`/api/v2/providers/credentials/${id}/default-fallback`, { method: 'PUT' }),
  clearDefaultFallback: (id: number) =>
    request(`/api/v2/providers/credentials/${id}/default-fallback`, { method: 'DELETE' }),
  setCredentialEnabled: (id: number, enabled: boolean) =>
    request<{ status: string; enabled: boolean }>(
      `/api/v2/providers/credentials/${id}/enabled`,
      { method: 'PUT', body: JSON.stringify({ enabled }) }
    ),
  setChainEntryEnabled: (chainEntryId: number, enabled: boolean) =>
    request<{ status: string; enabled: boolean }>(
      `/api/v2/providers/chains/entry/${chainEntryId}/enabled`,
      { method: 'PUT', body: JSON.stringify({ enabled }) }
    ),
  cleanSlate: () =>
    request<{ status: string; data: { tables: string[]; secrets_deleted: number } }>(
      '/api/v2/providers/_admin/clean-slate',
      { method: 'POST' }
    ),
  health: (id: number, limit = 50) =>
    request<{ data: any[] }>(`/api/v2/providers/health/${id}?limit=${limit}`),
  marketplace: () => request<{ data: any[] }>('/api/v2/providers/marketplace'),
  probeAll: () =>
    request<{ data: any[]; summary: { total: number; ok: number } }>(
      '/api/v2/providers/health/probe-all', { method: 'POST' }
    ),
  routes: (scope = 'workspace', scope_id?: string) => {
    const q = new URLSearchParams({ scope });
    if (scope_id) q.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/providers/routes?${q}`);
  },
  upsertRoute: (category: string, body: {
    policy: string; scope?: string; scope_id?: string;
    primary_credential_id?: number | null; fallback_chain?: number[]; custom_rules?: object;
  }) =>
    request<{ id: number }>(`/api/v2/providers/routes/${category}`, {
      method: 'PUT', body: JSON.stringify({ scope: 'workspace', fallback_chain: [], ...body }),
    }),
  quotas: (scope = 'workspace', scope_id?: string) => {
    const q = new URLSearchParams({ scope });
    if (scope_id) q.set('scope_id', scope_id);
    return request<{ data: any[] }>(`/api/v2/providers/quotas?${q}`);
  },
  createQuota: (body: {
    monthly_cap_usd: number; alert_pct?: number; hard_limit?: boolean;
    scope?: string; scope_id?: string; category?: string;
  }) =>
    request<{ id: number }>('/api/v2/providers/quotas', { method: 'POST', body: JSON.stringify(body) }),
  updateQuota: (id: number, body: { monthly_cap_usd: number; alert_pct?: number; hard_limit?: boolean }) =>
    request(`/api/v2/providers/quotas/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteQuota: (id: number) =>
    request(`/api/v2/providers/quotas/${id}`, { method: 'DELETE' }),
  auditLog: (params?: { category?: string; credential_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.credential_id) q.set('credential_id', String(params.credential_id));
    if (params?.limit) q.set('limit', String(params.limit));
    return request<{ data: any[] }>(`/api/v2/providers/audit-log?${q}`);
  },
  reorderChain: (items: { id: number; position: number }[]) =>
    request('/api/v2/providers/chains/reorder', { method: 'PATCH', body: JSON.stringify({ items }) }),
  deleteWorkspace: (workspace_id: number) =>
    request(`/api/v2/auth/workspaces/${workspace_id}`, { method: 'DELETE' }),
  sandboxRun: (body: {
    credential_id: number; capability: string;
    prompt?: string; text?: string; input_payload?: object;
  }) =>
    request<{ status: string; data: { run_id: number; ok: boolean; latency_ms: number; cost_usd: number | null; output: unknown; error: string | null } }>(
      '/api/v2/providers/sandbox/run', { method: 'POST', body: JSON.stringify(body) }
    ),
  sandboxRuns: (credential_id?: number, limit = 20) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (credential_id) q.set('credential_id', String(credential_id));
    return request<{ data: any[] }>(`/api/v2/providers/sandbox/runs?${q}`);
  },
};

export const changeRequestsApi = {
  list: (params?: { status?: string; category?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.category) q.set('category', params.category);
    return request<{ status: string; data: ChangeRequest[] }>(`/api/v2/providers/change-requests?${q}`);
  },
  create: (body: {
    request_type: ChangeRequestType;
    category: string;
    provider_name?: string;
    payload?: Record<string, unknown>;
    reason: string;
  }) =>
    request<{ status: string; data: { id: number } }>('/api/v2/providers/change-requests', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  get: (id: number) =>
    request<{ status: string; data: ChangeRequest }>(`/api/v2/providers/change-requests/${id}`),
  adminReview: (id: number, action: 'approve_forward' | 'reject', note?: string) =>
    request<{ status: string; data: { new_status: string } }>(
      `/api/v2/providers/change-requests/${id}/admin-review`,
      { method: 'POST', body: JSON.stringify({ action, note }) },
    ),
  ownerReview: (id: number, action: 'approve' | 'reject', note?: string) =>
    request<{ status: string; data: { new_status: string } }>(
      `/api/v2/providers/change-requests/${id}/owner-review`,
      { method: 'POST', body: JSON.stringify({ action, note }) },
    ),
};

export const youtubeOAuthApi = {
  authUrl: () => '/api/v2/providers/youtube/auth',
  status: () =>
    request<{ status: string; data: YouTubeOAuthStatus }>('/api/v2/providers/youtube/status'),
  disconnect: () =>
    request('/api/v2/providers/youtube/disconnect', { method: 'DELETE' }),
};
