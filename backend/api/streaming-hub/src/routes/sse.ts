import type { FastifyInstance, FastifyRequest } from "fastify";
import type { Hub, Event } from "../hub.js";

const KEEPALIVE_MS = 15_000;

/**
 * SSE endpoint — a long-lived HTTP GET that streams events to the client.
 *
 * Query parameters:
 *   - workspace_id (required): only events for this workspace are streamed
 *   - event_types (optional, comma-separated): filter by event type
 *   - token (optional): JWT — if not provided via header, taken from ?token=
 *
 * Emits SSE frames: `data: <json>\n\n` plus periodic `: keepalive` comments.
 */
export function registerSseRoutes(app: FastifyInstance, hub: Hub): void {
  app.get("/api/v2/stream/events", async (request, reply) => {
    const authed = await authenticate(app, request);
    if (!authed) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    const query = request.query as {
      workspace_id?: string;
      event_types?: string;
    };

    if (!query.workspace_id) {
      return reply.code(400).send({
        error: "Bad Request",
        message: "workspace_id query parameter is required",
      });
    }

    // Client can only stream events for its own workspace
    if (authed.workspace_id !== query.workspace_id) {
      return reply.code(403).send({
        error: "Forbidden",
        message: "Cannot stream events for another workspace",
      });
    }

    const eventTypes = query.event_types
      ? query.event_types.split(",").map((s) => s.trim()).filter(Boolean)
      : undefined;

    // Raw response for SSE — bypass Fastify serialization
    reply.raw.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    });
    reply.hijack();

    const push = (event: Event) => {
      const line = `id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
      reply.raw.write(line);
    };

    const keepalive = setInterval(() => {
      reply.raw.write(`: keepalive ${Date.now()}\n\n`);
    }, KEEPALIVE_MS);

    const subId = hub.subscribe(
      { workspaceId: query.workspace_id, eventTypes },
      push,
      () => {
        clearInterval(keepalive);
        reply.raw.end();
      }
    );

    // Send initial "connected" event so client knows the stream is live
    push({
      id: `sys-${Date.now()}`,
      type: "stream.connected",
      workspace_id: query.workspace_id,
      ts: Date.now(),
      data: { subscriber_id: subId },
    });

    request.raw.on("close", () => {
      clearInterval(keepalive);
      hub.unsubscribe(subId);
    });
  });
}

interface AuthedPrincipal {
  user_id: string;
  workspace_id: string;
}

async function authenticate(
  app: FastifyInstance,
  request: FastifyRequest
): Promise<AuthedPrincipal | null> {
  const query = request.query as { token?: string };
  const headerToken = extractBearer(request.headers.authorization);
  const token = headerToken || query.token;
  if (!token) return null;
  try {
    const decoded = await app.jwt.verify<AuthedPrincipal>(token);
    return {
      user_id: decoded.user_id,
      workspace_id: decoded.workspace_id,
    };
  } catch {
    return null;
  }
}

function extractBearer(header?: string): string | undefined {
  if (!header) return undefined;
  const [scheme, value] = header.split(" ");
  if (scheme?.toLowerCase() !== "bearer") return undefined;
  return value;
}
