"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.notifyApi = void 0;
var client_1 = require("./client");
exports.notifyApi = {
    list: function (unread_only, severity, limit) {
        if (unread_only === void 0) { unread_only = false; }
        if (limit === void 0) { limit = 100; }
        var q = new URLSearchParams({ unread_only: String(unread_only), limit: String(limit) });
        if (severity)
            q.set('severity', severity);
        return (0, client_1.request)("/api/v2/notifications?".concat(q));
    },
    read: function (id) { return (0, client_1.request)("/api/v2/notifications/".concat(id, "/read"), { method: 'POST' }); },
    routes: function () { return (0, client_1.request)('/api/v2/notifications/routes'); },
    upsertRoute: function (body) { return (0, client_1.request)('/api/v2/notifications/routes', { method: 'POST', body: JSON.stringify(body) }); },
    updateRoute: function (id, body) { return (0, client_1.request)("/api/v2/notifications/routes/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
    deleteRoute: function (id) { return (0, client_1.request)("/api/v2/notifications/routes/".concat(id), { method: 'DELETE' }); },
    deliveries: function (notification_id, limit) {
        if (limit === void 0) { limit = 100; }
        var q = new URLSearchParams({ limit: String(limit) });
        if (notification_id)
            q.set('notification_id', String(notification_id));
        return (0, client_1.request)("/api/v2/notifications/deliveries?".concat(q));
    },
};
