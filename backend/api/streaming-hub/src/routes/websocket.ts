import type { FastifyInstance } from "fastify";
import type { Hub, Event } from "../hub.js";

const HEARTBEAT_INTERVAL_MS = 20_000;
const HEARTBEAT_TIMEOUT_MS = 60_000;

/**
 * WebSocket endpoint — real-time bidirectional stream.
 *
 * Auth via `?token=<jwt>` query parameter (WebSockets can't send auth headers
 * in browser).
 *
 * Client → server messages (JSON):
 *   { "action": "subscribe", "event_types": ["job.progress", ...] }
 *   { "action": "ping" }
 *
 * Server → client messages (JSON):
 *   Events (as-is)
 *   { "type": "ack", "action": "subscribe", "event_types": [...] }
 *   { "type": "pong", "ts": <ms> }
 *   { "type": "error", "message": "..." }
 */
export async function registerWsRoutes(app: FastifyInstance, hub: Hub): Promise<void> {
  app.get("/api/v2/ws/events", { websocket: true }, async (socket, request) => {
    const query = request.query as { token?: string };
    if (!query.token) {
      socket.send(JSON.stringify({ type: "error", message: "token required" }));
      socket.close(4401, "Unauthorized");
      return;
    }

    let principal: { user_id: string; workspace_id: string };
    try {
      principal = await app.jwt.verify(query.token);
    } catch {
      socket.send(JSON.stringify({ type: "error", message: "invalid token" }));
      socket.close(4401, "Unauthorized");
      return;
    }

    let currentEventTypes: string[] | undefined = undefined;
    let subId: string | null = null;
    let lastSeenAt = Date.now();

    const applySubscription = (types?: string[]) => {
      if (subId) hub.unsubscribe(subId);
      currentEventTypes = types;
      subId = hub.subscribe(
        { workspaceId: principal.workspace_id, eventTypes: types },
        (event: Event) => {
          if (socket.readyState === socket.OPEN) {
            try {
              socket.send(JSON.stringify(event));
            } catch (err) {
              request.log.warn({ err }, "streaming.ws_send_failed");
            }
          }
        },
        () => {
          if (socket.readyState === socket.OPEN) socket.close();
        }
      );
    };

    // Default: subscribe to all events for this workspace
    applySubscription();

    socket.send(
      JSON.stringify({
        type: "stream.connected",
        workspace_id: principal.workspace_id,
        subscriber_id: subId,
      })
    );

    // Server-driven heartbeat — keeps proxies from closing idle
    // connections, and detects a dead client so we can free the sub.
    const heartbeat = setInterval(() => {
      const idleMs = Date.now() - lastSeenAt;
      if (idleMs > HEARTBEAT_TIMEOUT_MS) {
        request.log.warn({ idleMs }, "streaming.ws_heartbeat_timeout");
        try {
          socket.close(4408, "heartbeat timeout");
        } catch {
          /* noop */
        }
        return;
      }
      if (socket.readyState !== socket.OPEN) return;
      try {
        socket.send(JSON.stringify({ type: "heartbeat", ts: Date.now() }));
      } catch (err) {
        request.log.warn({ err }, "streaming.ws_heartbeat_send_failed");
      }
    }, HEARTBEAT_INTERVAL_MS);

    socket.on("message", async (raw: Buffer | string) => {
      lastSeenAt = Date.now();
      let msg: {
        action?: string;
        event_types?: string[];
        content_id?: string;
        last_event_id?: string;
      } = {};
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        socket.send(JSON.stringify({ type: "error", message: "invalid json" }));
        return;
      }
      if (msg.action === "subscribe") {
        applySubscription(msg.event_types);
        socket.send(
          JSON.stringify({
            type: "ack",
            action: "subscribe",
            event_types: currentEventTypes ?? [],
          })
        );
      } else if (msg.action === "resume" && msg.content_id) {
        // Backfill missed events since ``last_event_id`` (or from the
        // start of the retained stream if omitted).
        try {
          const missed = await hub.replaySince(msg.content_id, msg.last_event_id ?? "0");
          for (const evt of missed) {
            if (socket.readyState === socket.OPEN) socket.send(JSON.stringify(evt));
          }
          socket.send(
            JSON.stringify({
              type: "ack",
              action: "resume",
              replayed: missed.length,
            })
          );
        } catch (err) {
          request.log.warn({ err }, "streaming.ws_resume_failed");
          socket.send(JSON.stringify({ type: "error", message: "resume failed" }));
        }
      } else if (msg.action === "ping") {
        socket.send(JSON.stringify({ type: "pong", ts: Date.now() }));
      }
    });

    socket.on("close", () => {
      clearInterval(heartbeat);
      if (subId) hub.unsubscribe(subId);
    });
  });
}
