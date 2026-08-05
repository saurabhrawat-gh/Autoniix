"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.invitesApi = exports.membersApi = exports.projectsApi = exports.campaignsApi = exports.seriesApi = exports.brandsApi = exports.settingsApi = exports.workspaceApi = void 0;
var client_1 = require("./client");
exports.workspaceApi = {
    get: function () { return (0, client_1.request)('/api/v2/workspace'); },
    update: function (body) { return (0, client_1.request)('/api/v2/workspace', { method: 'PUT', body: JSON.stringify(body) }); },
    setMode: function (mode) { return (0, client_1.request)('/api/v2/workspace', { method: 'PUT', body: JSON.stringify({ mode: mode }) }); },
    getIntegrations: function () {
        return (0, client_1.request)('/api/v2/workspace/integrations');
    },
    updateIntegrations: function (body) {
        return (0, client_1.request)('/api/v2/workspace/integrations', { method: 'PUT', body: JSON.stringify(body) });
    },
};
exports.settingsApi = {
    get: function (scope, scope_id) {
        return (0, client_1.request)("/api/v2/workspace/settings?scope=".concat(encodeURIComponent(scope), "&scope_id=").concat(encodeURIComponent(scope_id)));
    },
    set: function (scope, scope_id, key, value, locked) {
        if (locked === void 0) { locked = false; }
        return (0, client_1.request)('/api/v2/workspace/settings', {
            method: 'PUT',
            body: JSON.stringify({ scope: scope, scope_id: scope_id, key: key, value: value, locked: locked }),
        });
    },
};
exports.brandsApi = {
    list: function () { return (0, client_1.request)('/api/v2/workspace/brands'); },
    get: function (id) { return (0, client_1.request)("/api/v2/workspace/brands/".concat(id)); },
    create: function (body) { return (0, client_1.request)('/api/v2/workspace/brands', { method: 'POST', body: JSON.stringify(body) }); },
    update: function (id, body) { return (0, client_1.request)("/api/v2/workspace/brands/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
};
exports.seriesApi = {
    list: function (channel_id) {
        return (0, client_1.request)("/api/v2/workspace/series".concat(channel_id ? "?channel_id=".concat(channel_id) : ''));
    },
    create: function (body) { return (0, client_1.request)('/api/v2/workspace/series', { method: 'POST', body: JSON.stringify(body) }); },
    update: function (id, body) { return (0, client_1.request)("/api/v2/workspace/series/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
    delete: function (id) { return (0, client_1.request)("/api/v2/workspace/series/".concat(id), { method: 'DELETE' }); },
};
exports.campaignsApi = {
    list: function (brand_id, status) {
        var p = new URLSearchParams();
        if (brand_id)
            p.set('brand_id', String(brand_id));
        if (status)
            p.set('status', status);
        return (0, client_1.request)("/api/v2/workspace/campaigns?".concat(p));
    },
    create: function (body) { return (0, client_1.request)('/api/v2/workspace/campaigns', { method: 'POST', body: JSON.stringify(body) }); },
    update: function (id, body) { return (0, client_1.request)("/api/v2/workspace/campaigns/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
};
exports.projectsApi = {
    list: function (params) {
        if (params === void 0) { params = {}; }
        var p = new URLSearchParams();
        Object.entries(params).forEach(function (_a) {
            var k = _a[0], v = _a[1];
            return v !== undefined && p.set(k, String(v));
        });
        return (0, client_1.request)("/api/v2/workspace/projects?".concat(p));
    },
    get: function (id) { return (0, client_1.request)("/api/v2/workspace/projects/".concat(id)); },
    create: function (body) { return (0, client_1.request)('/api/v2/workspace/projects', { method: 'POST', body: JSON.stringify(body) }); },
    update: function (id, body) { return (0, client_1.request)("/api/v2/workspace/projects/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
    delete: function (id) { return (0, client_1.request)("/api/v2/workspace/projects/".concat(id), { method: 'DELETE' }); },
};
exports.membersApi = {
    list: function () { return (0, client_1.request)('/api/v2/workspace/members'); },
    setRole: function (user_id, role) {
        return (0, client_1.request)("/api/v2/workspace/members/".concat(user_id, "/role"), { method: 'PUT', body: JSON.stringify({ role: role }) });
    },
    remove: function (user_id) { return (0, client_1.request)("/api/v2/workspace/members/".concat(user_id), { method: 'DELETE' }); },
    transferOwnership: function (new_owner_user_id, current_password) {
        return (0, client_1.request)('/api/v2/workspace/transfer-ownership', {
            method: 'POST',
            body: JSON.stringify({ new_owner_user_id: new_owner_user_id, current_password: current_password }),
        });
    },
};
exports.invitesApi = {
    list: function () { return (0, client_1.request)('/api/v2/workspace/invites'); },
    create: function (email, role, expires_days) {
        if (expires_days === void 0) { expires_days = 7; }
        return (0, client_1.request)('/api/v2/workspace/invites', { method: 'POST', body: JSON.stringify({ email: email, role: role, expires_days: expires_days }) });
    },
    revoke: function (id) { return (0, client_1.request)("/api/v2/workspace/invites/".concat(id), { method: 'DELETE' }); },
};
