"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.channelsApi = void 0;
var client_1 = require("./client");
exports.channelsApi = {
    list: function (includeArchived) {
        if (includeArchived === void 0) { includeArchived = false; }
        return (0, client_1.request)("/api/v2/channels?include_archived=".concat(includeArchived));
    },
    get: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id)); },
    create: function (body) { return (0, client_1.request)('/api/v2/channels', { method: 'POST', body: JSON.stringify(body) }); },
    patch: function (id, body) { return (0, client_1.request)("/api/v2/channels/".concat(id), { method: 'PUT', body: JSON.stringify(body) }); },
    upsertProfile: function (id, payload) {
        return (0, client_1.request)("/api/v2/channels/".concat(id, "/profile"), { method: 'PUT', body: JSON.stringify({ payload: payload }) });
    },
    presets: function () { return (0, client_1.request)('/api/v2/channels/presets'); },
    addPillar: function (id, body) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/pillars"), { method: 'POST', body: JSON.stringify(body) }); },
    deletePillar: function (id, pid) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/pillars/").concat(pid), { method: 'DELETE' }); },
    addRule: function (id, body) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/topic-rules"), { method: 'POST', body: JSON.stringify(body) }); },
    deleteRule: function (id, rid) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/topic-rules/").concat(rid), { method: 'DELETE' }); },
    addReference: function (id, body) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/references"), { method: 'POST', body: JSON.stringify(body) }); },
    deleteReference: function (id, rid) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/references/").concat(rid), { method: 'DELETE' }); },
    fieldSuggest: function (field, context) {
        if (context === void 0) { context = {}; }
        return (0, client_1.request)('/api/v2/channels/ai/field-suggest', { method: 'POST', body: JSON.stringify({ field: field, context: context }) });
    },
    draftCreate: function (current_step, payload) {
        return (0, client_1.request)('/api/v2/channels/drafts', { method: 'POST', body: JSON.stringify({ current_step: current_step, payload: payload }) });
    },
    draftSave: function (id, current_step, payload) {
        return (0, client_1.request)("/api/v2/channels/drafts/".concat(id), { method: 'PUT', body: JSON.stringify({ current_step: current_step, payload: payload }) });
    },
    draftGet: function (id) { return (0, client_1.request)("/api/v2/channels/drafts/".concat(id)); },
    enable: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/enable"), { method: 'PUT' }); },
    disable: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/disable"), { method: 'PUT' }); },
    archive: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/archive"), { method: 'PUT' }); },
    restore: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/restore"), { method: 'PUT' }); },
    delete: function (id, body) {
        return (0, client_1.request)("/api/v2/channels/".concat(id), { method: 'DELETE', body: JSON.stringify(body) });
    },
    clone: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/clone"), { method: 'POST' }); },
    export: function (id) { return (0, client_1.request)("/api/v2/channels/".concat(id, "/export")); },
    trigger: function (id, body) {
        if (body === void 0) { body = {}; }
        return (0, client_1.request)("/api/v2/channels/".concat(id, "/trigger"), { method: 'POST', body: JSON.stringify(body) });
    },
    pauseJob: function (channelId, contentId) {
        return (0, client_1.request)("/api/v2/channels/".concat(channelId, "/jobs/").concat(contentId, "/pause"), { method: 'POST' });
    },
    resumeJob: function (channelId, contentId) {
        return (0, client_1.request)("/api/v2/channels/".concat(channelId, "/jobs/").concat(contentId, "/resume"), { method: 'POST' });
    },
    stopJob: function (channelId, contentId) {
        return (0, client_1.request)("/api/v2/channels/".concat(channelId, "/jobs/").concat(contentId, "/stop"), { method: 'POST' });
    },
};
