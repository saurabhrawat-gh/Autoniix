"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.youtubeOAuthApi = exports.changeRequestsApi = exports.providersApi = void 0;
var client_1 = require("./client");
exports.providersApi = {
    categories: function () { return (0, client_1.request)('/api/v2/providers/categories'); },
    kinds: function () { return (0, client_1.request)('/api/v2/providers/kinds'); },
    createKind: function (body) {
        return (0, client_1.request)('/api/v2/providers/kinds', { method: 'POST', body: JSON.stringify(body) });
    },
    deleteKind: function (kind) {
        return (0, client_1.request)("/api/v2/providers/kinds/".concat(encodeURIComponent(kind)), { method: 'DELETE' });
    },
    createCategory: function (body) {
        return (0, client_1.request)('/api/v2/providers/categories', { method: 'POST', body: JSON.stringify(body) });
    },
    deleteCategory: function (name) {
        return (0, client_1.request)("/api/v2/providers/categories/".concat(encodeURIComponent(name)), { method: 'DELETE' });
    },
    updateCategory: function (name, label) {
        return (0, client_1.request)("/api/v2/providers/categories/".concat(encodeURIComponent(name)), { method: 'PATCH', body: JSON.stringify({ label: label }) });
    },
    createMarketplaceProvider: function (body) {
        return (0, client_1.request)('/api/v2/providers/marketplace', { method: 'POST', body: JSON.stringify(body) });
    },
    deleteMarketplaceProvider: function (provider_key) {
        return (0, client_1.request)("/api/v2/providers/marketplace/".concat(encodeURIComponent(provider_key)), { method: 'DELETE' });
    },
    catalogForCategory: function (category) {
        return (0, client_1.request)("/api/v2/providers/catalog-for-category?category=".concat(encodeURIComponent(category)));
    },
    restoreDefaults: function () {
        return (0, client_1.request)('/api/v2/providers/restore-defaults', { method: 'POST' });
    },
    credentials: function (category) {
        return (0, client_1.request)("/api/v2/providers/credentials".concat(category ? "?category=".concat(category) : ''));
    },
    createCredential: function (body) {
        return (0, client_1.request)('/api/v2/providers/credentials', { method: 'POST', body: JSON.stringify(body) });
    },
    updateCredential: function (id, body) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id), { method: 'PUT', body: JSON.stringify(body) });
    },
    deleteCredential: function (id) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id), { method: 'DELETE' });
    },
    testCredential: function (id) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/test"), { method: 'POST' });
    },
    rotateCredential: function (id, secret_value, secret_key, hint) {
        if (secret_key === void 0) { secret_key = 'api_key'; }
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/rotate"), {
            method: 'POST',
            body: JSON.stringify({ secret_value: secret_value, secret_key: secret_key, hint: hint }),
        });
    },
    createCredentialFromWizard: function (body) {
        return (0, client_1.request)('/api/v2/providers/credentials/from-wizard', { method: 'POST', body: JSON.stringify(body) });
    },
    setupChecklist: function () {
        return (0, client_1.request)('/api/v2/providers/setup-checklist');
    },
    rotationStatus: function (id) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/rotation-status"));
    },
    allRotationStatus: function (params) {
        var q = new URLSearchParams();
        if (params === null || params === void 0 ? void 0 : params.category)
            q.set('category', params.category);
        if (params === null || params === void 0 ? void 0 : params.overdue_only)
            q.set('overdue_only', 'true');
        return (0, client_1.request)("/api/v2/providers/credentials/rotation-status".concat(q.toString() ? '?' + q : ''));
    },
    chain: function (category) { return (0, client_1.request)("/api/v2/providers/chains/".concat(category)); },
    setChain: function (category, credential_ids) {
        return (0, client_1.request)("/api/v2/providers/chains/".concat(category), {
            method: 'PUT',
            body: JSON.stringify({ credential_ids: credential_ids }),
        });
    },
    chainsV2: function (params) {
        var q = new URLSearchParams();
        if (params.scope)
            q.set('scope', params.scope);
        if (params.scope_id)
            q.set('scope_id', params.scope_id);
        if (params.content_mode)
            q.set('content_mode', params.content_mode);
        if (params.category)
            q.set('category', params.category);
        return (0, client_1.request)("/api/v2/providers/chains?".concat(q));
    },
    upsertChainV2: function (body) {
        return (0, client_1.request)("/api/v2/providers/chains", { method: 'PUT', body: JSON.stringify(body) });
    },
    deleteChainV2: function (params) {
        var q = new URLSearchParams({ scope: params.scope, category: params.category });
        if (params.scope_id)
            q.set('scope_id', params.scope_id);
        if (params.content_mode)
            q.set('content_mode', params.content_mode);
        return (0, client_1.request)("/api/v2/providers/chains?".concat(q), { method: 'DELETE' });
    },
    resolved: function (params) {
        var q = new URLSearchParams({ category: params.category });
        if (params.channel_id)
            q.set('channel_id', params.channel_id);
        if (params.content_mode)
            q.set('content_mode', params.content_mode);
        return (0, client_1.request)("/api/v2/providers/resolved?".concat(q));
    },
    contentModes: function () {
        return (0, client_1.request)('/api/v2/providers/content-modes');
    },
    healthStreamUrl: function (category) {
        var q = new URLSearchParams();
        if (category)
            q.set('category', category);
        return "/api/v2/providers/health-stream?".concat(q);
    },
    registeredProviders: function (category) {
        return (0, client_1.request)("/api/v2/providers/registered?category=".concat(encodeURIComponent(category)));
    },
    supportedModels: function (category, provider_name) {
        var q = new URLSearchParams({ category: category, provider_name: provider_name });
        return (0, client_1.request)("/api/v2/providers/models?".concat(q));
    },
    setDefaultFallback: function (id) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/default-fallback"), { method: 'PUT' });
    },
    clearDefaultFallback: function (id) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/default-fallback"), { method: 'DELETE' });
    },
    setCredentialEnabled: function (id, enabled) {
        return (0, client_1.request)("/api/v2/providers/credentials/".concat(id, "/enabled"), { method: 'PUT', body: JSON.stringify({ enabled: enabled }) });
    },
    setChainEntryEnabled: function (chainEntryId, enabled) {
        return (0, client_1.request)("/api/v2/providers/chains/entry/".concat(chainEntryId, "/enabled"), { method: 'PUT', body: JSON.stringify({ enabled: enabled }) });
    },
    cleanSlate: function () {
        return (0, client_1.request)('/api/v2/providers/_admin/clean-slate', { method: 'POST' });
    },
    health: function (id, limit) {
        if (limit === void 0) { limit = 50; }
        return (0, client_1.request)("/api/v2/providers/health/".concat(id, "?limit=").concat(limit));
    },
    marketplace: function () { return (0, client_1.request)('/api/v2/providers/marketplace'); },
    probeAll: function () {
        return (0, client_1.request)('/api/v2/providers/health/probe-all', { method: 'POST' });
    },
    routes: function (scope, scope_id) {
        if (scope === void 0) { scope = 'workspace'; }
        var q = new URLSearchParams({ scope: scope });
        if (scope_id)
            q.set('scope_id', scope_id);
        return (0, client_1.request)("/api/v2/providers/routes?".concat(q));
    },
    upsertRoute: function (category, body) {
        return (0, client_1.request)("/api/v2/providers/routes/".concat(category), {
            method: 'PUT', body: JSON.stringify(__assign({ scope: 'workspace', fallback_chain: [] }, body)),
        });
    },
    quotas: function (scope, scope_id) {
        if (scope === void 0) { scope = 'workspace'; }
        var q = new URLSearchParams({ scope: scope });
        if (scope_id)
            q.set('scope_id', scope_id);
        return (0, client_1.request)("/api/v2/providers/quotas?".concat(q));
    },
    createQuota: function (body) {
        return (0, client_1.request)('/api/v2/providers/quotas', { method: 'POST', body: JSON.stringify(body) });
    },
    updateQuota: function (id, body) {
        return (0, client_1.request)("/api/v2/providers/quotas/".concat(id), { method: 'PUT', body: JSON.stringify(body) });
    },
    deleteQuota: function (id) {
        return (0, client_1.request)("/api/v2/providers/quotas/".concat(id), { method: 'DELETE' });
    },
    auditLog: function (params) {
        var q = new URLSearchParams();
        if (params === null || params === void 0 ? void 0 : params.category)
            q.set('category', params.category);
        if (params === null || params === void 0 ? void 0 : params.credential_id)
            q.set('credential_id', String(params.credential_id));
        if (params === null || params === void 0 ? void 0 : params.limit)
            q.set('limit', String(params.limit));
        return (0, client_1.request)("/api/v2/providers/audit-log?".concat(q));
    },
    reorderChain: function (items) {
        return (0, client_1.request)('/api/v2/providers/chains/reorder', { method: 'PATCH', body: JSON.stringify({ items: items }) });
    },
    deleteWorkspace: function (workspace_id) {
        return (0, client_1.request)("/api/v2/auth/workspaces/".concat(workspace_id), { method: 'DELETE' });
    },
    sandboxRun: function (body) {
        return (0, client_1.request)('/api/v2/providers/sandbox/run', { method: 'POST', body: JSON.stringify(body) });
    },
    sandboxRuns: function (credential_id, limit) {
        if (limit === void 0) { limit = 20; }
        var q = new URLSearchParams({ limit: String(limit) });
        if (credential_id)
            q.set('credential_id', String(credential_id));
        return (0, client_1.request)("/api/v2/providers/sandbox/runs?".concat(q));
    },
};
exports.changeRequestsApi = {
    list: function (params) {
        var q = new URLSearchParams();
        if (params === null || params === void 0 ? void 0 : params.status)
            q.set('status', params.status);
        if (params === null || params === void 0 ? void 0 : params.category)
            q.set('category', params.category);
        return (0, client_1.request)("/api/v2/providers/change-requests?".concat(q));
    },
    create: function (body) {
        return (0, client_1.request)('/api/v2/providers/change-requests', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    },
    get: function (id) {
        return (0, client_1.request)("/api/v2/providers/change-requests/".concat(id));
    },
    adminReview: function (id, action, note) {
        return (0, client_1.request)("/api/v2/providers/change-requests/".concat(id, "/admin-review"), { method: 'POST', body: JSON.stringify({ action: action, note: note }) });
    },
    ownerReview: function (id, action, note) {
        return (0, client_1.request)("/api/v2/providers/change-requests/".concat(id, "/owner-review"), { method: 'POST', body: JSON.stringify({ action: action, note: note }) });
    },
};
exports.youtubeOAuthApi = {
    authUrl: function () { return '/api/v2/providers/youtube/auth'; },
    status: function () {
        return (0, client_1.request)('/api/v2/providers/youtube/status');
    },
    disconnect: function () {
        return (0, client_1.request)('/api/v2/providers/youtube/disconnect', { method: 'DELETE' });
    },
};
