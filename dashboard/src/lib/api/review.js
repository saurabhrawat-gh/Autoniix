"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.reviewConfigApi = exports.reviewApi = void 0;
var client_1 = require("./client");
exports.reviewApi = {
    queue: function (state, channel_id, limit) {
        if (state === void 0) { state = 'pending'; }
        if (limit === void 0) { limit = 100; }
        var q = new URLSearchParams({ state: state, limit: String(limit) });
        if (channel_id)
            q.set('channel_id', channel_id);
        return (0, client_1.request)("/api/v2/review/queue?".concat(q));
    },
    get: function (video_id) { return (0, client_1.request)("/api/v2/review/".concat(video_id)); },
    open: function (video_id) { return (0, client_1.request)("/api/v2/review/".concat(video_id, "/open"), { method: 'POST' }); },
    decide: function (video_id, decision, summary) {
        return (0, client_1.request)("/api/v2/review/".concat(video_id, "/decide"), {
            method: 'POST',
            body: JSON.stringify({ decision: decision, summary: summary }),
        });
    },
    editScript: function (video_id, body) {
        return (0, client_1.request)("/api/v2/review/".concat(video_id, "/script/edit"), { method: 'POST', body: JSON.stringify(body) });
    },
    regenThumb: function (video_id, prompt_nudge) {
        return (0, client_1.request)("/api/v2/review/".concat(video_id, "/thumbnail/regenerate"), {
            method: 'POST',
            body: JSON.stringify({ prompt_nudge: prompt_nudge, keep_current: true }),
        });
    },
    comment: function (video_id, body) {
        return (0, client_1.request)("/api/v2/review/".concat(video_id, "/comments"), { method: 'POST', body: JSON.stringify(body) });
    },
    updateTitle: function (video_id, body) {
        return (0, client_1.request)("/api/v2/review/".concat(video_id, "/title"), { method: 'PUT', body: JSON.stringify(body) });
    },
};
exports.reviewConfigApi = {
    get: function (channelId) {
        return (0, client_1.request)("/api/v2/channels/".concat(encodeURIComponent(channelId), "/settings/review"));
    },
    update: function (channelId, body) {
        return (0, client_1.request)("/api/v2/channels/".concat(encodeURIComponent(channelId), "/settings/review"), {
            method: 'PUT',
            body: JSON.stringify(body),
        });
    },
};
