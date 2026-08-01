import type { FastifyInstance } from "fastify";

// Stub routes for remaining modules
// These return 501 Not Implemented until migrated from Rust

export async function stubRoutes(app: FastifyInstance): Promise<void> {
  const stub = async (request: any, reply: any) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ 
      error: "Not Implemented",
      message: "This endpoint is not yet implemented in gateway v2"
    });
  };

  // Experiments
  app.get("/api/v2/experiments", stub);
  app.post("/api/v2/experiments", stub);
  app.get("/api/v2/experiments/:id", stub);
  app.patch("/api/v2/experiments/:id", stub);
  app.delete("/api/v2/experiments/:id", stub);

  // Finishing
  app.get("/api/v2/finishing", stub);
  app.post("/api/v2/finishing", stub);
  app.get("/api/v2/finishing/:id", stub);

  // Feature Flags
  app.get("/api/v2/flags", stub);
  app.post("/api/v2/flags", stub);
  app.patch("/api/v2/flags/:id", stub);

  // Library
  app.get("/api/v2/library", stub);
  app.post("/api/v2/library", stub);
  app.get("/api/v2/library/:id", stub);
  app.delete("/api/v2/library/:id", stub);

  // Lookup Values
  app.get("/api/v2/lookup-values", stub);
  app.post("/api/v2/lookup-values", stub);
  app.patch("/api/v2/lookup-values/:id", stub);
  app.delete("/api/v2/lookup-values/:id", stub);

  // Providers
  app.get("/api/v2/providers", stub);
  app.post("/api/v2/providers", stub);
  app.get("/api/v2/providers/:id", stub);
  app.patch("/api/v2/providers/:id", stub);
  app.delete("/api/v2/providers/:id", stub);

  // Provider Chains
  app.get("/api/v2/provider-chains", stub);
  app.post("/api/v2/provider-chains", stub);
  app.get("/api/v2/provider-chains/:id", stub);
  app.patch("/api/v2/provider-chains/:id", stub);
  app.delete("/api/v2/provider-chains/:id", stub);

  // Review
  app.get("/api/v2/review", stub);
  app.post("/api/v2/review/:id/approve", stub);
  app.post("/api/v2/review/:id/reject", stub);

  // System
  app.get("/api/v2/system/health", stub);
  app.get("/api/v2/system/stats", stub);
  app.get("/api/v2/system/config", stub);

  // Voice
  app.get("/api/v2/voice", stub);
  app.post("/api/v2/voice", stub);
  app.get("/api/v2/voice/:id", stub);
  app.patch("/api/v2/voice/:id", stub);
  app.delete("/api/v2/voice/:id", stub);

  // Proxy operations
  app.post("/api/v2/proxy/trigger", stub);
  app.post("/api/v2/proxy/clone", stub);
  app.post("/api/v2/proxy/pause", stub);
  app.post("/api/v2/proxy/resume", stub);
  app.post("/api/v2/proxy/stop", stub);
}
