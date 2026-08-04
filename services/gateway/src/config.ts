import { z } from "zod";

const ConfigSchema = z.object({
  nodeEnv: z.enum(["development", "production", "test"]).default("development"),
  port: z.coerce.number().int().min(1).max(65535).default(8080),
  logLevel: z.enum(["fatal", "error", "warn", "info", "debug", "trace"]).default("info"),
  
  databaseUrl: z.string().url(),
  
  jwtSecret: z.string().min(32),
  jwtExpiresIn: z.string().default("15m"),
  refreshTokenExpiresIn: z.string().default("7d"),
  
  corsOrigin: z.string().default("http://localhost:3000"),
  
  rateLimitMax: z.coerce.number().int().min(1).default(100),
  rateLimitWindow: z.coerce.number().int().min(1000).default(60000),
});

export type Config = z.infer<typeof ConfigSchema>;

export function loadConfig(): Config {
  return ConfigSchema.parse({
    nodeEnv: process.env.NODE_ENV,
    port: process.env.PORT,
    logLevel: process.env.LOG_LEVEL,
    databaseUrl: process.env.DATABASE_URL,
    jwtSecret: process.env.JWT_SECRET,
    jwtExpiresIn: process.env.JWT_EXPIRES_IN,
    refreshTokenExpiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN,
    corsOrigin: process.env.CORS_ORIGIN,
    rateLimitMax: process.env.RATE_LIMIT_MAX,
    rateLimitWindow: process.env.RATE_LIMIT_WINDOW,
  });
}
