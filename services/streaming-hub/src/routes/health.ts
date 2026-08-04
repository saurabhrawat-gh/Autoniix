import type { FastifyInstance } from "fastify";
import type { Hub } from "../hub.js";

export function registerHealthRoutes(app: FastifyInstance, hub: Hub): void {
  app.get("/health", async () => ({
    status: "healthy",
    version: "2.0.0",
    subscribers: hub.subscriberCount,
    timestamp: new Date().toISOString(),
  }));

  app.get("/ready", async () => ({
    status: "ready",
    version: "2.0.0",
  }));
}
