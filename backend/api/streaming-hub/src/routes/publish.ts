import type { FastifyInstance } from "fastify";
import { z } from "zod";
import type { Hub } from "../hub.js";

const PublishBodySchema = z.object({
  type: z.string().min(1),
  workspace_id: z.string().min(1),
  data: z.record(z.string(), z.unknown()).optional(),
  id: z.string().optional(),
  ts: z.number().int().optional(),
});

/**
 * Internal publisher endpoint. Called by Python services or gateway-v2 to
 * broadcast an event. Requires a valid JWT (any authenticated principal for
 * that workspace can publish).
 *
 * Consider protecting this with a service-to-service secret in production
 * if you want to prevent user tokens from publishing arbitrary events.
 */
export function registerPublishRoutes(app: FastifyInstance, hub: Hub): void {
  app.post("/api/v2/stream/publish", async (request, reply) => {
    // Basic JWT gate
    try {
      await request.jwtVerify();
    } catch {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    const parsed = PublishBodySchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({
        error: "Bad Request",
        details: parsed.error.issues,
      });
    }

    const principal = (request.user ?? {}) as { workspace_id?: string };
    if (principal.workspace_id && principal.workspace_id !== parsed.data.workspace_id) {
      return reply.code(403).send({
        error: "Forbidden",
        message: "Cannot publish events for another workspace",
      });
    }

    const event = await hub.publish(parsed.data);
    return reply.code(202).send({ event });
  });
}
