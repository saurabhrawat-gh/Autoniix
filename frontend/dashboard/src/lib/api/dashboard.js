"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dashboardApi = void 0;
var client_1 = require("./client");
exports.dashboardApi = {
    stats: function () { return (0, client_1.request)('/api/v2/channels/stats'); },
    activeJobs: function (limit) {
        if (limit === void 0) { limit = 30; }
        var q = new URLSearchParams({ limit: String(limit) });
        return (0, client_1.request)("/api/v2/content?".concat(q));
    },
};
