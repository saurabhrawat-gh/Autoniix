"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.flagsApi = void 0;
var client_1 = require("./client");
exports.flagsApi = {
    list: function () { return (0, client_1.request)('/api/v2/flags'); },
    set: function (key, enabled, payload) {
        if (payload === void 0) { payload = {}; }
        return (0, client_1.request)("/api/v2/flags/".concat(key), { method: 'PUT', body: JSON.stringify({ enabled: enabled, payload: payload }) });
    },
};
