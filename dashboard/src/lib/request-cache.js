"use strict";
/**
 * Request dedup + TTL cache for the v2 API client.
 *
 * Added in hotfix #304 (AE-263) to neutralize the dashboard request-storm
 * observed on hover/scroll/tab-focus/component-remount. Without this layer
 * the dashboard fires the same GET 5–10× within milliseconds (no
 * deduplication, no client cache, no `Cache-Control`).
 *
 * Behaviour:
 *   - In-flight coalescence: if a request with the same key is already
 *     in flight, return its promise (N callers ⇒ 1 network call).
 *   - TTL cache: if a response was fetched within `DEFAULT_TTL_MS`, return
 *     the cached value without touching the network.
 *   - Mutations bypass this layer and call `invalidateCache()` afterwards.
 *
 * Trade-off:
 *   TTL is intentionally short (5s). Long enough to absorb hover/scroll/
 *   remount storms; short enough that stale-data UX is never noticeable.
 *   Cross-tab mutations may show up to 5s of stale data — acceptable.
 *
 * This module is intentionally framework-agnostic (no React deps) so it
 * can be unit-tested under plain Node without a test runner.
 */
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
exports.DEFAULT_TTL_MS = void 0;
exports.dedupedGet = dedupedGet;
exports.invalidateCache = invalidateCache;
exports._resetCacheForTest = _resetCacheForTest;
exports._cacheSizeForTest = _cacheSizeForTest;
var inFlight = new Map();
var responseCache = new Map();
exports.DEFAULT_TTL_MS = 5000;
/**
 * Coalesce concurrent identical requests and serve from a short TTL cache.
 *
 * @param key      Stable cache key (e.g. `"GET /api/v2/workspaces"`)
 * @param executor Function that performs the actual network call
 * @param ttlMs    How long to cache a successful response (default 5s)
 */
function dedupedGet(key_1, executor_1) {
    return __awaiter(this, arguments, void 0, function (key, executor, ttlMs) {
        var now, cached, existing, promise;
        var _this = this;
        if (ttlMs === void 0) { ttlMs = exports.DEFAULT_TTL_MS; }
        return __generator(this, function (_a) {
            now = Date.now();
            cached = responseCache.get(key);
            if (cached && cached.expiresAt > now) {
                return [2 /*return*/, cached.value];
            }
            existing = inFlight.get(key);
            if (existing) {
                return [2 /*return*/, existing];
            }
            promise = (function () { return __awaiter(_this, void 0, void 0, function () {
                var value;
                return __generator(this, function (_a) {
                    switch (_a.label) {
                        case 0:
                            _a.trys.push([0, , 2, 3]);
                            return [4 /*yield*/, executor()];
                        case 1:
                            value = _a.sent();
                            responseCache.set(key, { value: value, expiresAt: Date.now() + ttlMs });
                            return [2 /*return*/, value];
                        case 2:
                            inFlight.delete(key);
                            return [7 /*endfinally*/];
                        case 3: return [2 /*return*/];
                    }
                });
            }); })();
            inFlight.set(key, promise);
            return [2 /*return*/, promise];
        });
    });
}
/**
 * Invalidate cached responses.
 *
 * - No arg → clear everything (called after any mutation as a safe default).
 * - `keyPrefix` → clear only keys starting with the prefix (future use).
 *
 * In-flight requests are NOT cancelled — they will complete and write their
 * result to the cache. Subsequent reads will use that fresh value.
 */
function invalidateCache(keyPrefix) {
    if (!keyPrefix) {
        responseCache.clear();
        return;
    }
    for (var _i = 0, _a = Array.from(responseCache.keys()); _i < _a.length; _i++) {
        var k = _a[_i];
        if (k.startsWith(keyPrefix))
            responseCache.delete(k);
    }
}
// --- Test-only hooks (not part of the public contract) ---------------------
/** @internal */
function _resetCacheForTest() {
    responseCache.clear();
    inFlight.clear();
}
/** @internal */
function _cacheSizeForTest() {
    return { responses: responseCache.size, inFlight: inFlight.size };
}
