"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.damApi = exports.libraryApi = void 0;
var client_1 = require("./client");
exports.libraryApi = {
    assets: function (params) {
        if (params === void 0) { params = {}; }
        var p = new URLSearchParams();
        Object.entries(params).forEach(function (_a) {
            var k = _a[0], v = _a[1];
            return v !== undefined && p.set(k, String(v));
        });
        return (0, client_1.request)("/api/v2/library/assets?".concat(p));
    },
    brand: function (channel_id) {
        return (0, client_1.request)("/api/v2/library/brand".concat(channel_id ? "?channel_id=".concat(channel_id) : ''));
    },
    music: function () { return (0, client_1.request)("/api/v2/library/music"); },
};
exports.damApi = {
    list: function (params) {
        if (params === void 0) { params = {}; }
        var p = new URLSearchParams();
        Object.entries(params).forEach(function (_a) {
            var k = _a[0], v = _a[1];
            return v !== undefined && p.set(k, String(v));
        });
        return (0, client_1.request)("/api/v2/library/dam/assets?".concat(p));
    },
    preflight: function (sha256) {
        return (0, client_1.request)("/api/v2/library/dam/assets/preflight?sha256=".concat(sha256), { method: 'POST' });
    },
    get: function (id) {
        return (0, client_1.request)("/api/v2/library/dam/assets/".concat(id));
    },
    patch: function (id, body) {
        return (0, client_1.request)("/api/v2/library/dam/assets/".concat(id), { method: 'PATCH', body: JSON.stringify(body) });
    },
    delete: function (id) {
        return (0, client_1.request)("/api/v2/library/dam/assets/".concat(id), { method: 'DELETE' });
    },
    tags: function (scope, scope_id) {
        if (scope === void 0) { scope = 'workspace'; }
        var p = new URLSearchParams({ scope: scope });
        if (scope_id)
            p.set('scope_id', scope_id);
        return (0, client_1.request)("/api/v2/library/dam/tags?".concat(p));
    },
    search: function (body) {
        return (0, client_1.request)('/api/v2/library/dam/search', { method: 'POST', body: JSON.stringify(body) });
    },
    collections: function (scope, scope_id) {
        if (scope === void 0) { scope = 'workspace'; }
        var p = new URLSearchParams({ scope: scope });
        if (scope_id)
            p.set('scope_id', scope_id);
        return (0, client_1.request)("/api/v2/library/dam/collections?".concat(p));
    },
    createCollection: function (body) {
        return (0, client_1.request)('/api/v2/library/dam/collections', { method: 'POST', body: JSON.stringify(body) });
    },
    updateCollection: function (id, body) {
        return (0, client_1.request)("/api/v2/library/dam/collections/".concat(id), { method: 'PUT', body: JSON.stringify(body) });
    },
    deleteCollection: function (id) {
        return (0, client_1.request)("/api/v2/library/dam/collections/".concat(id), { method: 'DELETE' });
    },
    brandKits: function (scope, scope_id) {
        if (scope === void 0) { scope = 'brand'; }
        var p = new URLSearchParams({ scope: scope });
        if (scope_id)
            p.set('scope_id', scope_id);
        return (0, client_1.request)("/api/v2/library/dam/brand-kits?".concat(p));
    },
    createBrandKit: function (body) {
        return (0, client_1.request)('/api/v2/library/dam/brand-kits', { method: 'POST', body: JSON.stringify(body) });
    },
    updateBrandKit: function (id, body) {
        return (0, client_1.request)("/api/v2/library/dam/brand-kits/".concat(id), { method: 'PUT', body: JSON.stringify(body) });
    },
};
