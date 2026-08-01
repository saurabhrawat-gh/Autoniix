import type { FastifyInstance } from "fastify";

export async function notificationRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/v2/notifications", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.patch("/api/v2/notifications/:id/read", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.post("/api/v2/notifications/mark-all-read", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });
}
