import { describe, it, expect, beforeAll, afterAll } from "vitest";
import type { FastifyInstance } from "fastify";
import { createApp } from "../src/app.js";
import type { Config } from "../src/config.js";

const testConfig: Config = {
  port: 0,
  nodeEnv: "test",
  logLevel: "fatal",
  databaseUrl: process.env.DATABASE_URL || "postgresql://autoniix:autoniix@localhost:5432/autoniix_test",
  jwtSecret: "test-secret-must-be-at-least-32-characters-long",
  jwtExpiresIn: "1h",
  refreshTokenExpiresIn: "30d",
  corsOrigin: "http://localhost:3000",
  rateLimitMax: 1000,
  rateLimitWindow: 60000,
};

describe("Gateway v2 Smoke Tests", () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await createApp(testConfig);
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  describe("Health endpoints", () => {
    it("GET /health returns 200 or 503", async () => {
      const response = await app.inject({ method: "GET", url: "/health" });
      expect([200, 503]).toContain(response.statusCode);
      const body = response.json();
      expect(body).toHaveProperty("status");
      expect(body).toHaveProperty("version");
    });

    it("GET /ready returns 200 or 503", async () => {
      const response = await app.inject({ method: "GET", url: "/ready" });
      expect([200, 503]).toContain(response.statusCode);
    });
  });

  describe("Auth endpoints", () => {
    it("GET /api/v2/auth/me without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/auth/me",
      });
      expect(response.statusCode).toBe(401);
    });

    it("POST /api/v2/auth/login with invalid body returns 400", async () => {
      const response = await app.inject({
        method: "POST",
        url: "/api/v2/auth/login",
        payload: { email: "not-an-email" },
      });
      expect([400, 401]).toContain(response.statusCode);
    });
  });

  describe("Job endpoints require auth", () => {
    it("GET /api/v2/jobs without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/jobs",
      });
      expect(response.statusCode).toBe(401);
    });

    it("POST /api/v2/jobs without token returns 401", async () => {
      const response = await app.inject({
        method: "POST",
        url: "/api/v2/jobs",
        payload: {},
      });
      expect(response.statusCode).toBe(401);
    });
  });

  describe("Channel endpoints require auth", () => {
    it("GET /api/v2/channels without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/channels",
      });
      expect(response.statusCode).toBe(401);
    });
  });

  describe("Content endpoints require auth", () => {
    it("GET /api/v2/content without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/content",
      });
      expect(response.statusCode).toBe(401);
    });
  });

  describe("Workspace endpoints require auth", () => {
    it("GET /api/v2/workspace without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/workspace",
      });
      expect(response.statusCode).toBe(401);
    });
  });

  describe("Notifications require auth", () => {
    it("GET /api/v2/notifications without token returns 401", async () => {
      const response = await app.inject({
        method: "GET",
        url: "/api/v2/notifications",
      });
      expect(response.statusCode).toBe(401);
    });
  });
});
