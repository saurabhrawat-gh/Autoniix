import type { FastifyInstance } from "fastify";

export async function userRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/v2/users/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.patch("/api/v2/users/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.delete("/api/v2/users/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });
}
