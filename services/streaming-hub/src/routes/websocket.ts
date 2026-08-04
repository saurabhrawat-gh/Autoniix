import type { FastifyInstance } from "fastify";
import type { Hub, Event } from "../hub.js";

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
export async function registerWsRoutes(
  app: FastifyInstance,
  hub: Hub
): Promise<void> {
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

    const applySubscription = (types?: string[]) => {
      if (subId) hub.unsubscribe(subId);
      currentEventTypes = types;
      subId = hub.subscribe(
        { workspaceId: principal.workspace_id, eventTypes: types },
        (event: Event) => {
          if (socket.readyState === socket.OPEN) {
            socket.send(JSON.stringify(event));
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

    socket.on("message", (raw: Buffer | string) => {
      let msg: { action?: string; event_types?: string[] } = {};
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
      } else if (msg.action === "ping") {
        socket.send(JSON.stringify({ type: "pong", ts: Date.now() }));
      }
    });

    socket.on("close", () => {
      if (subId) hub.unsubscribe(subId);
    });
  });
}
