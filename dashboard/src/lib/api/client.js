"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.BASE = void 0;
exports.readToken = readToken;
exports.refreshOnce = refreshOnce;
exports.rawRequest = rawRequest;
exports._apiError = _apiError;
exports.request = request;
exports.isLoggedIn = isLoggedIn;
exports.setToken = setToken;
exports.clearToken = clearToken;
exports.wsProgress = wsProgress;
exports.wsEvents = wsEvents;
exports.legacyLogin = legacyLogin;
/**
 * v2 API client — shared HTTP infrastructure.
 *
 * v2 auth uses HttpOnly cookies (set by the backend on login/refresh).
 * Cookies are sent automatically via credentials:'include'.
 * No auth tokens are stored in localStorage.
 *
 * Request layer (hotfix #304 / AE-263):
 *   GET requests are routed through `dedupedGet()` from `./request-cache` to
 *   coalesce in-flight duplicates and serve a short TTL cache. This neutralises
 *   the hover/scroll/remount request-storm. Mutations bypass the cache and
 *   invalidate it on completion.
 */
var request_cache_1 = require("../request-cache");
exports.BASE = process.env.NEXT_PUBLIC_API_URL || '';
// One-time purge: remove any legacy localStorage token keys left from old builds.
if (typeof window !== 'undefined') {
    localStorage.removeItem('dashboard_token');
    localStorage.removeItem('dashboard_token_expires');
}
function readToken() {
    if (typeof window === 'undefined')
        return null;
    return localStorage.getItem('dashboard_token');
}
var _refreshing = null;
function refreshOnce() {
    return __awaiter(this, void 0, void 0, function () {
        var _this = this;
        return __generator(this, function (_a) {
            if (_refreshing)
                return [2 /*return*/, _refreshing];
            _refreshing = (function () { return __awaiter(_this, void 0, void 0, function () {
                var res, _a;
                return __generator(this, function (_b) {
                    switch (_b.label) {
                        case 0:
                            _b.trys.push([0, 2, 3, 4]);
                            return [4 /*yield*/, fetch("".concat(exports.BASE, "/api/v2/auth/refresh"), {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    credentials: 'include',
                                })];
                        case 1:
                            res = _b.sent();
                            if (res.ok)
                                return [2 /*return*/, true];
                            return [2 /*return*/, false];
                        case 2:
                            _a = _b.sent();
                            return [2 /*return*/, false];
                        case 3:
                            _refreshing = null;
                            return [7 /*endfinally*/];
                        case 4: return [2 /*return*/];
                    }
                });
            }); })();
            return [2 /*return*/, _refreshing];
        });
    });
}
function rawRequest(path_1) {
    return __awaiter(this, arguments, void 0, function (path, opts, _isRetry) {
        var headers, res, refreshed, body, wRes, wData, next, _a, body;
        if (opts === void 0) { opts = {}; }
        if (_isRetry === void 0) { _isRetry = false; }
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    headers = __assign({ 'Content-Type': 'application/json', 'X-Source': 'ui' }, (opts.headers || {}));
                    return [4 /*yield*/, fetch("".concat(exports.BASE).concat(path), __assign(__assign({}, opts), { headers: headers, credentials: 'include' }))];
                case 1:
                    res = _b.sent();
                    if (!(res.status === 401)) return [3 /*break*/, 4];
                    if (!!_isRetry) return [3 /*break*/, 3];
                    return [4 /*yield*/, refreshOnce()];
                case 2:
                    refreshed = _b.sent();
                    if (refreshed)
                        return [2 /*return*/, rawRequest(path, opts, true)];
                    _b.label = 3;
                case 3:
                    if (typeof window !== 'undefined')
                        window.location.href = '/login';
                    throw new Error('Unauthorized');
                case 4:
                    if (!(res.status === 403)) return [3 /*break*/, 14];
                    return [4 /*yield*/, res.json().catch(function () { return ({}); })];
                case 5:
                    body = _b.sent();
                    if (!(body.detail === 'workspace_access_revoked' && typeof window !== 'undefined')) return [3 /*break*/, 13];
                    _b.label = 6;
                case 6:
                    _b.trys.push([6, 11, , 12]);
                    return [4 /*yield*/, fetch("".concat(exports.BASE, "/api/v2/auth/workspaces"), { headers: headers, credentials: 'include' })];
                case 7:
                    wRes = _b.sent();
                    if (!wRes.ok) return [3 /*break*/, 10];
                    return [4 /*yield*/, wRes.json()];
                case 8:
                    wData = _b.sent();
                    next = wData.data.find(function (w) { return !w.active; });
                    if (!next) return [3 /*break*/, 10];
                    return [4 /*yield*/, fetch("".concat(exports.BASE, "/api/v2/auth/switch-workspace"), {
                            method: 'POST',
                            headers: headers,
                            credentials: 'include',
                            body: JSON.stringify({ workspace_id: next.id }),
                        })];
                case 9:
                    _b.sent();
                    window.location.href = '/dashboard';
                    throw new Error('workspace_access_revoked');
                case 10: return [3 /*break*/, 12];
                case 11:
                    _a = _b.sent();
                    return [3 /*break*/, 12];
                case 12:
                    window.location.href = '/login?reason=no_workspace_access';
                    throw new Error('workspace_access_revoked');
                case 13: throw _apiError(res.status, body);
                case 14:
                    if (!!res.ok) return [3 /*break*/, 16];
                    return [4 /*yield*/, res.json().catch(function () { return ({}); })];
                case 15:
                    body = _b.sent();
                    throw _apiError(res.status, body);
                case 16: return [2 /*return*/, res.json()];
            }
        });
    });
}
/**
 * Build an Error that preserves the server's structured `{detail: {code, message}}`
 * shape. Without this, callers that do `e.detail.code` see undefined and
 * `e.message` becomes the literal string "[object Object]".
 */
function _apiError(status, body) {
    var b = body;
    var detail = b === null || b === void 0 ? void 0 : b.detail;
    var message;
    if (typeof detail === 'string')
        message = detail;
    else if (detail && typeof detail === 'object') {
        var d = detail;
        message = d.message || d.code || (b === null || b === void 0 ? void 0 : b.error) || "HTTP ".concat(status);
    }
    else {
        message = (b === null || b === void 0 ? void 0 : b.error) || "HTTP ".concat(status);
    }
    var err = new Error(message);
    err.status = status;
    if (detail !== undefined)
        err.detail = detail;
    if (detail && typeof detail === 'object' && typeof detail.code === 'string') {
        err.code = detail.code;
    }
    return err;
}
/**
 * Cache-aware request wrapper (hotfix #304 / AE-263).
 *
 * - GET → routed through `dedupedGet()`: in-flight coalescence + 5s TTL cache.
 * - Mutations → call `rawRequest()` directly and invalidate cache on success.
 */
function request(path_1) {
    return __awaiter(this, arguments, void 0, function (path, opts) {
        var method, result;
        if (opts === void 0) { opts = {}; }
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    method = (opts.method || 'GET').toUpperCase();
                    if (!(method !== 'GET')) return [3 /*break*/, 2];
                    return [4 /*yield*/, rawRequest(path, opts)];
                case 1:
                    result = _a.sent();
                    (0, request_cache_1.invalidateCache)();
                    return [2 /*return*/, result];
                case 2: return [2 /*return*/, (0, request_cache_1.dedupedGet)("GET ".concat(path), function () { return rawRequest(path, opts); })];
            }
        });
    });
}
// Session utilities
function isLoggedIn() {
    if (typeof window === 'undefined')
        return false;
    return document.cookie.split(';').some(function (c) { return c.trim() === 'auth_status=1'; });
}
function setToken(token, expiresIn) {
    if (typeof window === 'undefined')
        return;
    localStorage.setItem('dashboard_token', token);
    if (expiresIn) {
        localStorage.setItem('dashboard_token_expires', String(Date.now() + expiresIn * 1000));
    }
}
function clearToken() {
    if (typeof window === 'undefined')
        return;
    localStorage.removeItem('dashboard_token');
    localStorage.removeItem('dashboard_token_expires');
}
// WebSocket helpers
function wsProgress(contentId) {
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var host = process.env.NEXT_PUBLIC_WS_URL || "".concat(proto, "//").concat(window.location.host);
    return new WebSocket("".concat(host, "/api/ws/progress/").concat(contentId));
}
function wsEvents() {
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var host = process.env.NEXT_PUBLIC_WS_URL || "".concat(proto, "//").concat(window.location.host);
    return new WebSocket("".concat(host, "/api/ws/events"));
}
// Legacy password-only login (used when auth.v2.enabled = FALSE).
function legacyLogin(password) {
    return __awaiter(this, void 0, void 0, function () {
        var res, body, b, data;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [4 /*yield*/, fetch("".concat(exports.BASE, "/api/auth/login"), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: password }),
                    })];
                case 1:
                    res = _a.sent();
                    if (!!res.ok) return [3 /*break*/, 3];
                    return [4 /*yield*/, res.json().catch(function () { return ({}); })];
                case 2:
                    body = _a.sent();
                    b = body;
                    throw new Error(b.detail || b.error || "HTTP ".concat(res.status));
                case 3: return [4 /*yield*/, res.json()];
                case 4:
                    data = _a.sent();
                    setToken(data.token, data.expires_in);
                    return [2 /*return*/];
            }
        });
    });
}
