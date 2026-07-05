"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.experimentsApi = void 0;
var client_1 = require("./client");
exports.experimentsApi = {
    list: function (status) {
        if (status === void 0) { status = ''; }
        return (0, client_1.request)("/api/v2/experiments?status=".concat(status));
    },
    create: function (body) { return (0, client_1.request)('/api/v2/experiments', { method: 'POST', body: JSON.stringify(body) }); },
    activate: function (name) { return (0, client_1.request)("/api/v2/experiments/".concat(encodeURIComponent(name), "/activate"), { method: 'POST' }); },
    pause: function (name) { return (0, client_1.request)("/api/v2/experiments/".concat(encodeURIComponent(name), "/pause"), { method: 'POST' }); },
    complete: function (name, w) {
        if (w === void 0) { w = ''; }
        return (0, client_1.request)("/api/v2/experiments/".concat(encodeURIComponent(name), "/complete?winner=").concat(encodeURIComponent(w)), { method: 'POST' });
    },
    results: function (name) { return (0, client_1.request)("/api/v2/experiments/".concat(encodeURIComponent(name), "/results")); },
};
