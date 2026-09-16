"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.jobsApi = void 0;
var client_1 = require("./client");
exports.jobsApi = {
    active: function () { return (0, client_1.request)('/api/v2/jobs/active'); },
    progress: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/progress")); },
    output: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/output")); },
    metadata: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/metadata")); },
    approve: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/approve"), { method: 'POST' }); },
    reject: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/reject"), { method: 'POST' }); },
    retry: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/retry"), { method: 'POST' }); },
    restart: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/restart"), { method: 'POST' }); },
    pause: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/pause"), { method: 'POST' }); },
    resume: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/resume"), { method: 'POST' }); },
    stop: function (id) { return (0, client_1.request)("/api/v2/jobs/".concat(encodeURIComponent(id), "/stop"), { method: 'POST' }); },
};
