import Fastify, { type FastifyInstance } from "fastify";
import fastifyJwt from "@fastify/jwt";
import fastifyWebsocket from "@fastify/websocket";
import { Hub } from "./hub.js";
import { registerHealthRoutes } from "./routes/health.js";
import { registerSseRoutes } from "./routes/sse.js";
import { registerWsRoutes } from "./routes/websocket.js";
import { registerPublishRoutes } from "./routes/publish.js";
import type { Config } from "./config.js";

declare module "fastify" {
  interface FastifyInstance {
    hub: Hub;
  }
}

export async function createApp(config: Config): Promise<FastifyInstance> {
  const app = Fastify({
    logger: {
      level: config.logLevel,
      transport:
        config.nodeEnv === "development"
          ? { target: "pino-pretty" }
          : undefined,
    },
    trustProxy: true,
  });

  await app.register(fastifyJwt, { secret: config.jwtSecret });
  await app.register(fastifyWebsocket);

  const hub = new Hub(config.redisUrl, app.log);
  await hub.start();
  app.decorate("hub", hub);

  registerHealthRoutes(app, hub);
  registerSseRoutes(app, hub);
  await registerWsRoutes(app, hub);
  registerPublishRoutes(app, hub);

  app.addHook("onClose", async () => {
    await hub.stop();
  });

  return app;
}
