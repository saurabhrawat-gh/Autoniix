"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.finishingApi = exports.resolveChainApi = exports.resolveConfigApi = exports.lookupValuesApi = void 0;
var client_1 = require("./client");
exports.lookupValuesApi = {
    list: function (type, parent_value) {
        var q = new URLSearchParams();
        if (type)
            q.set('type', type);
        if (parent_value)
            q.set('parent_value', parent_value);
        return (0, client_1.request)("/api/v2/lookup-values?".concat(q));
    },
    createGlobal: function (body) {
        return (0, client_1.request)('/api/v2/lookup-values', { method: 'POST', body: JSON.stringify(body) });
    },
    createWorkspace: function (body) {
        return (0, client_1.request)('/api/v2/workspace/lookup-values', { method: 'POST', body: JSON.stringify(body) });
    },
    update: function (id, body) {
        return (0, client_1.request)("/api/v2/lookup-values/".concat(id), { method: 'PATCH', body: JSON.stringify(body) });
    },
    deactivate: function (id) {
        return (0, client_1.request)("/api/v2/lookup-values/".concat(id), { method: 'DELETE' });
    },
};
exports.resolveConfigApi = {
    get: function (channelId, content_mode) {
        var q = content_mode ? "?content_mode=".concat(content_mode) : '';
        return (0, client_1.request)("/api/v2/channels/".concat(encodeURIComponent(channelId), "/resolve-config").concat(q));
    },
};
exports.resolveChainApi = {
    get: function (category, opts) {
        var q = new URLSearchParams({ category: category });
        if (opts === null || opts === void 0 ? void 0 : opts.content_mode)
            q.set('content_mode', opts.content_mode);
        if (opts === null || opts === void 0 ? void 0 : opts.channel_id)
            q.set('channel_id', opts.channel_id);
        return (0, client_1.request)("/api/v2/workspace/resolve-provider-chain?".concat(q));
    },
};
exports.finishingApi = {
    get: function (channelId) {
        return (0, client_1.request)("/api/v2/channels/".concat(encodeURIComponent(channelId), "/settings/finishing"));
    },
    update: function (channelId, body) {
        return (0, client_1.request)("/api/v2/channels/".concat(encodeURIComponent(channelId), "/settings/finishing"), {
            method: 'PUT',
            body: JSON.stringify(body),
        });
    },
    presets: function () { return (0, client_1.request)('/api/v2/finishing/presets'); },
};
