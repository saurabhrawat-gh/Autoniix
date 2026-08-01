import type { FastifyInstance } from "fastify";

export async function channelRoutes(app: FastifyInstance): Promise<void> {
  // GET /api/v2/channels - List channels
  app.get("/api/v2/channels", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Channel listing not yet implemented" });
  });

  // POST /api/v2/channels - Create channel
  app.post("/api/v2/channels", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Channel creation not yet implemented" });
  });

  // GET /api/v2/channels/:id - Get channel
  app.get("/api/v2/channels/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Channel retrieval not yet implemented" });
  });

  // PATCH /api/v2/channels/:id - Update channel
  app.patch("/api/v2/channels/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Channel update not yet implemented" });
  });

  // DELETE /api/v2/channels/:id - Delete channel
  app.delete("/api/v2/channels/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Channel deletion not yet implemented" });
  });
}
