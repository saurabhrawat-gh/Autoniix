"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.contentApi = void 0;
var client_1 = require("./client");
exports.contentApi = {
    list: function (params) {
        var q = new URLSearchParams();
        Object.entries(params).forEach(function (_a) {
            var k = _a[0], v = _a[1];
            return v !== undefined && v !== null && q.set(k, String(v));
        });
        return (0, client_1.request)("/api/v2/content?".concat(q));
    },
    search: function (q, channel_id, limit) {
        if (limit === void 0) { limit = 40; }
        var p = new URLSearchParams({ q: q, limit: String(limit) });
        if (channel_id)
            p.set('channel_id', channel_id);
        return (0, client_1.request)("/api/v2/content/search?".concat(p));
    },
    bulk: function (action, ids, note) {
        return (0, client_1.request)('/api/v2/content/bulk', {
            method: 'POST',
            body: JSON.stringify({ action: action, ids: ids, note: note }),
        });
    },
    calendar: function (start, end, channel_id) {
        var q = new URLSearchParams({ start: start, end: end });
        if (channel_id)
            q.set('channel_id', channel_id);
        return (0, client_1.request)("/api/v2/content/calendar?".concat(q));
    },
    detail: function (contentId) {
        return (0, client_1.request)("/api/v2/content/".concat(encodeURIComponent(contentId)));
    },
    stats: function (channel_id, period) {
        if (period === void 0) { period = 'week'; }
        var q = new URLSearchParams({ period: period });
        if (channel_id)
            q.set('channel_id', channel_id);
        return (0, client_1.request)("/api/v2/content/stats?".concat(q));
    },
    trigger: function (body) {
        return (0, client_1.request)('/api/v2/content/trigger', { method: 'POST', body: JSON.stringify(body) });
    },
    triggerHistory: function (channel_id, limit) {
        if (limit === void 0) { limit = 20; }
        var q = new URLSearchParams({ limit: String(limit) });
        if (channel_id)
            q.set('channel_id', channel_id);
        return (0, client_1.request)("/api/v2/content/triggers/history?".concat(q));
    },
};
