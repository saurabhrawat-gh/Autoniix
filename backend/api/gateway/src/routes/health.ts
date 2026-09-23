import type { FastifyInstance } from "fastify";
import { healthCheck } from "../database.js";

export async function healthRoutes(app: FastifyInstance): Promise<void> {
  app.get("/health", async (request, reply) => {
    const dbHealthy = await healthCheck(app.db);

    if (!dbHealthy) {
      return reply.code(503).send({
        status: "unhealthy",
        version: "2.0.0",
        database: "down",
      });
    }

    return reply.send({
      status: "healthy",
      version: "2.0.0",
      database: "up",
      uptime: process.uptime(),
    });
  });

  app.get("/ready", async (request, reply) => {
    const dbHealthy = await healthCheck(app.db);

    if (!dbHealthy) {
      return reply.code(503).send({ ready: false });
    }

    return reply.send({ ready: true });
  });
}
