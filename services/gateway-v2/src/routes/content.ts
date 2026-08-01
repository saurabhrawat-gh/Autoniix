import type { FastifyInstance } from "fastify";

export async function contentRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/v2/content", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.post("/api/v2/content", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.get("/api/v2/content/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.patch("/api/v2/content/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.delete("/api/v2/content/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });
}
