/**
 * Centralized TanStack Query key factories (AE-595).
 *
 * Usage:
 *   useQuery({ queryKey: qk.channels.list(), queryFn: () => channelsApi.list() })
 *   queryClient.invalidateQueries({ queryKey: qk.channels.all })
 */

export const qk = {
  auth: {
    all: ['auth'] as const,
    me: () => ['auth', 'me'] as const,
    workspaces: () => ['auth', 'workspaces'] as const,
  },

  channels: {
    all: ['channels'] as const,
    list: (includeArchived = false) => ['channels', 'list', { includeArchived }] as const,
    detail: (id: string) => ['channels', 'detail', id] as const,
    stats: () => ['channels', 'stats'] as const,
    presets: () => ['channels', 'presets'] as const,
    reviewConfig: (id: string) => ['channels', 'reviewConfig', id] as const,
    finishingConfig: (id: string) => ['channels', 'finishingConfig', id] as const,
  },

  content: {
    all: ['content'] as const,
    list: (params: Record<string, unknown>) => ['content', 'list', params] as const,
    detail: (id: string) => ['content', 'detail', id] as const,
    calendar: (start: string, end: string, channelId?: string) =>
      ['content', 'calendar', { start, end, channelId }] as const,
    stats: (channelId?: string, period?: string) =>
      ['content', 'stats', { channelId, period }] as const,
    triggerHistory: (channelId?: string) => ['content', 'triggerHistory', channelId] as const,
  },

  jobs: {
    all: ['jobs'] as const,
    active: () => ['jobs', 'active'] as const,
    progress: (id: string) => ['jobs', 'progress', id] as const,
    output: (id: string) => ['jobs', 'output', id] as const,
    metadata: (id: string) => ['jobs', 'metadata', id] as const,
  },

  providers: {
    all: ['providers'] as const,
    categories: () => ['providers', 'categories'] as const,
    kinds: () => ['providers', 'kinds'] as const,
    marketplace: () => ['providers', 'marketplace'] as const,
    credentials: (category?: string) => ['providers', 'credentials', category] as const,
    credential: (id: number) => ['providers', 'credential', id] as const,
    chain: (category: string) => ['providers', 'chain', category] as const,
    chainsV2: (params: Record<string, unknown>) => ['providers', 'chainsV2', params] as const,
    resolved: (params: Record<string, unknown>) => ['providers', 'resolved', params] as const,
    checklist: () => ['providers', 'checklist'] as const,
    health: (id: number) => ['providers', 'health', id] as const,
    rotationStatus: (id?: number) => ['providers', 'rotationStatus', id] as const,
    routes: (scope?: string, scopeId?: string) => ['providers', 'routes', scope, scopeId] as const,
    quotas: (scope?: string, scopeId?: string) => ['providers', 'quotas', scope, scopeId] as const,
    sandboxRuns: (credentialId?: number) => ['providers', 'sandboxRuns', credentialId] as const,
    changeRequests: (params?: Record<string, unknown>) => ['providers', 'changeRequests', params] as const,
    contentModes: () => ['providers', 'contentModes'] as const,
    registeredProviders: (category: string) => ['providers', 'registered', category] as const,
    supportedModels: (category: string, providerName: string) =>
      ['providers', 'models', category, providerName] as const,
    youtube: {
      status: () => ['providers', 'youtube', 'status'] as const,
    },
  },

  review: {
    all: ['review'] as const,
    queue: (state?: string, channelId?: string) => ['review', 'queue', state, channelId] as const,
    detail: (videoId: string) => ['review', 'detail', videoId] as const,
  },

  dashboard: {
    all: ['dashboard'] as const,
    stats: () => ['dashboard', 'stats'] as const,
  },

  workspace: {
    all: ['workspace'] as const,
    get: () => ['workspace', 'get'] as const,
    integrations: () => ['workspace', 'integrations'] as const,
    settings: (scope: string, scopeId: string) => ['workspace', 'settings', scope, scopeId] as const,
    members: () => ['workspace', 'members'] as const,
    invites: () => ['workspace', 'invites'] as const,
    brands: () => ['workspace', 'brands'] as const,
    brand: (id: number) => ['workspace', 'brand', id] as const,
    series: (channelId?: string) => ['workspace', 'series', channelId] as const,
    campaigns: (brandId?: number, status?: string) => ['workspace', 'campaigns', brandId, status] as const,
    projects: (params?: Record<string, unknown>) => ['workspace', 'projects', params] as const,
    project: (id: number) => ['workspace', 'project', id] as const,
    resolveChain: (category: string, opts?: Record<string, unknown>) =>
      ['workspace', 'resolveChain', category, opts] as const,
  },

  system: {
    all: ['system'] as const,
    config: () => ['system', 'config'] as const,
    environment: () => ['system', 'environment'] as const,
    fleetHealth: () => ['system', 'fleetHealth'] as const,
  },

  notifications: {
    all: ['notifications'] as const,
    list: (unreadOnly?: boolean, severity?: string) =>
      ['notifications', 'list', unreadOnly, severity] as const,
    routes: () => ['notifications', 'routes'] as const,
    deliveries: (notificationId?: number) => ['notifications', 'deliveries', notificationId] as const,
  },

  library: {
    all: ['library'] as const,
    assets: (params?: Record<string, unknown>) => ['library', 'assets', params] as const,
    dam: {
      list: (params?: Record<string, unknown>) => ['library', 'dam', 'list', params] as const,
      detail: (id: number) => ['library', 'dam', 'detail', id] as const,
      tags: (scope?: string, scopeId?: string) => ['library', 'dam', 'tags', scope, scopeId] as const,
      collections: (scope?: string, scopeId?: string) =>
        ['library', 'dam', 'collections', scope, scopeId] as const,
      brandKits: (scope?: string, scopeId?: string) =>
        ['library', 'dam', 'brandKits', scope, scopeId] as const,
    },
  },

  users: {
    all: ['users'] as const,
    list: () => ['users', 'list'] as const,
  },

  flags: {
    all: ['flags'] as const,
    list: () => ['flags', 'list'] as const,
  },

  experiments: {
    all: ['experiments'] as const,
    list: (status?: string) => ['experiments', 'list', status] as const,
    results: (name: string) => ['experiments', 'results', name] as const,
  },

  lookup: {
    all: ['lookup'] as const,
    values: (type?: string, parentValue?: string) => ['lookup', 'values', type, parentValue] as const,
    resolveConfig: (channelId: string, contentMode?: string) =>
      ['lookup', 'resolveConfig', channelId, contentMode] as const,
    finishingPresets: () => ['lookup', 'finishingPresets'] as const,
  },

  voice: {
    all: ['voice'] as const,
    list: () => ['voice', 'list'] as const,
  },
} as const;
