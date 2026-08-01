import Fastify from "fastify";
import fastifyJwt from "@fastify/jwt";
import fastifyCookie from "@fastify/cookie";
import fastifyCors from "@fastify/cors";
import fastifyHelmet from "@fastify/helmet";
import fastifyRateLimit from "@fastify/rate-limit";
import { serializerCompiler, validatorCompiler, type ZodTypeProvider } from "@fastify/type-provider-zod";

import type { Config } from "./config.js";
import { createDatabase, type Database } from "./database.js";
import { healthRoutes } from "./routes/health.js";
import { authRoutes } from "./routes/auth.js";

declare module "fastify" {
  interface FastifyInstance {
    db: Database;
    config: Config;
  }
}

export async function createApp(config: Config) {
  const app = Fastify({
    logger: {
      level: config.logLevel,
      transport:
        config.nodeEnv === "development"
          ? {
              target: "pino-pretty",
              options: {
                translateTime: "HH:MM:ss Z",
                ignore: "pid,hostname",
              },
            }
          : undefined,
    },
  }).withTypeProvider<ZodTypeProvider>();

  app.setValidatorCompiler(validatorCompiler);
  app.setSerializerCompiler(serializerCompiler);

  const db = createDatabase(config);
  app.decorate("db", db);
  app.decorate("config", config);

  await app.register(fastifyHelmet, {
    contentSecurityPolicy: config.nodeEnv === "production",
  });

  await app.register(fastifyCors, {
    origin: config.corsOrigin,
    credentials: true,
  });

  await app.register(fastifyRateLimit, {
    max: config.rateLimitMax,
    timeWindow: config.rateLimitWindow,
  });

  await app.register(fastifyJwt, {
    secret: config.jwtSecret,
    sign: {
      expiresIn: config.jwtExpiresIn,
    },
  });

  await app.register(fastifyCookie, {
    secret: config.jwtSecret,
  });

  await app.register(healthRoutes);
  await app.register(authRoutes);
  
  const { jobRoutes } = await import("./routes/jobs.js");
  await app.register(jobRoutes);

  app.setErrorHandler((error: any, request, reply) => {
    request.log.error(error);

    if (error.validation) {
      return reply.code(400).send({
        error: "Validation Error",
        message: error.message,
        details: error.validation,
      });
    }

    if (error.statusCode) {
      return reply.code(error.statusCode).send({
        error: error.name,
        message: error.message,
      });
    }

    return reply.code(500).send({
      error: "Internal Server Error",
      message: config.nodeEnv === "production" ? "An unexpected error occurred" : error.message,
    });
  });

  return app;
}
