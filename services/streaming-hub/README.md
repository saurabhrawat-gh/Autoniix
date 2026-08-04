# Streaming Hub v2 (Node/Fastify)

**Status:** Phase 3 migration replacement for the legacy Go `streaming-hub`  
**Framework:** Fastify 5 + `@fastify/websocket` + `ioredis`  
**Ports:** 8090 (container), 8091 (local dev)

---

## Endpoints

### `GET /api/v2/stream/events` — Server-Sent Events

Long-lived HTTP GET streaming events to the browser.

**Query params:**
- `workspace_id` (required) — only events for this workspace are streamed
- `event_types` (optional, CSV) — filter by event type, e.g. `job.progress,job.completed`
- `token` (optional) — JWT (else use `Authorization: Bearer` header)

**Response:** `text/event-stream` frames plus periodic `: keepalive` comments.
Client's workspace (from JWT) must match `workspace_id`.

### `GET /api/v2/ws/events` — WebSocket

Real-time bidirectional stream. Auth via `?token=<jwt>` query parameter
(browsers can't send auth headers on the WS handshake).

**Client → server:**
- `{ "action": "subscribe", "event_types": [...] }` — refine filter
- `{ "action": "ping" }`

**Server → client:**
- Events as-is
- `{ "type": "ack", ... }`, `{ "type": "pong", "ts": ... }`, `{ "type": "error", ... }`

### `POST /api/v2/stream/publish` — Internal publisher

Any authenticated principal can publish events for its own workspace. Body:

```json
{ "type": "job.progress", "workspace_id": "ws-1", "data": { "pct": 42 } }
```

Returns `202 Accepted` with the enriched event (id + ts filled in).

### `GET /health` / `GET /ready`

Standard health probes. `/health` reports current subscriber count.

---

## Architecture

```
publisher → POST /publish → Hub.publish() ─┬─→ local fanout (in-process subs)
                                           └─→ Redis PUBLISH autoniix:events
                                                        │
                                    other instances ────┴─→ their local fanout
```

Multi-instance safe: each pod runs its own `Hub`, cross-instance events flow
via the shared Redis channel `autoniix:events`.

**Wire format** (JSON on Redis): matches the legacy Go hub, so both can
co-exist during rollout.

---

## Traefik Routing (Rollout)

`docker-compose.yml` defines a header-gated router:

```
Host($GW_DOMAIN) && PathPrefix(/api/v2/stream, /api/v2/ws) && Headers(X-Gateway-Version, v2)
```

- **Priority 100** — wins when `X-Gateway-Version: v2` is present
- **No default** — traffic without the header falls through to the legacy Go hub

**Rollout:**
1. `make sh2-up` — start alongside legacy hub
2. Add `X-Gateway-Version: v2` to dashboard requests
3. Watch subscriber count in `/health`
4. When happy, flip the router to priority 1 (always match) and stop the Go hub

**Instant rollback:** `make sh2-rollback`.

---

## Local Development

```bash
# Ensure Redis is running (from docker-compose or brew services)
export REDIS_URL=redis://localhost:6379
export JWT_SECRET=$(openssl rand -hex 32)
make sh2-dev
```

Or via workspaces from repo root:

```bash
npm run dev --workspace=@autoniix/streaming-hub-v2
```
