import type { FastifyInstance } from "fastify";
import {
  SignInRequestSchema,
  SignUpRequestSchema,
  RefreshTokenRequestSchema,
  type SignInRequest,
  type SignUpRequest,
  type RefreshTokenRequest,
  type Principal,
} from "@autoniix/contracts";
import { UserRepository } from "../repositories/user.repository.js";
import { PasswordManager } from "../utils/password.js";
import { JwtManager } from "../utils/jwt.js";
import { setAuthCookies, clearAuthCookies } from "../utils/cookies.js";

export async function authRoutes(app: FastifyInstance): Promise<void> {
  const userRepo = new UserRepository(app.db);
  const jwtManager = new JwtManager(app);

  app.post("/api/v2/auth/login", async (request, reply) => {
    try {
      const body = SignInRequestSchema.parse(request.body) as SignInRequest;
      const { email, password, workspace_id } = body;

      const user = await userRepo.findByEmail(email);
      if (!user) {
        return reply.code(401).send({
          error: "Unauthorized",
          message: "Invalid email or password",
        });
      }

      const isValid = await PasswordManager.verifyPassword(password, user.password_hash);
      if (!isValid) {
        return reply.code(401).send({
          error: "Unauthorized",
          message: "Invalid email or password",
        });
      }

      const workspaces = await userRepo.getUserWorkspaces(user.id);
      if (workspaces.length === 0) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "User has no workspace access",
        });
      }

      const targetWorkspace = workspace_id ? workspaces.find((w) => w.id === workspace_id) : workspaces[0];

      if (!targetWorkspace) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "User does not have access to the specified workspace",
        });
      }

      const membership = await userRepo.getWorkspaceMembership(user.id, targetWorkspace.id);

      const principal: Principal = {
        user_id: user.id,
        workspace_id: targetWorkspace.id,
        email: user.email,
        roles: membership ? [membership.role] : [],
        global_roles: [],
        permissions: [],
      };

      const accessToken = await jwtManager.createAccessToken(principal);
      const refreshToken = await jwtManager.createRefreshToken(principal);

      setAuthCookies(reply, accessToken, refreshToken);

      return reply.send({
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
        user: userRepo.toUser(user),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(400).send({
        error: "Bad Request",
        message: error.message,
      });
    }
  });

  app.post("/api/v2/auth/register", async (request, reply) => {
    try {
      const body = SignUpRequestSchema.parse(request.body) as SignUpRequest;
      const { email, password, full_name, workspace_name } = body;

      const existing = await userRepo.findByEmail(email);
      if (existing) {
        return reply.code(409).send({
          error: "Conflict",
          message: "User with this email already exists",
        });
      }

      const passwordHash = await PasswordManager.hashPassword(password);
      const user = await userRepo.create(email, passwordHash, full_name);
      const workspace = await userRepo.createWorkspace(workspace_name, user.id);

      const principal: Principal = {
        user_id: user.id,
        workspace_id: workspace.id,
        email: user.email,
        roles: ["owner"],
        global_roles: [],
        permissions: [],
      };

      const accessToken = await jwtManager.createAccessToken(principal);
      const refreshToken = await jwtManager.createRefreshToken(principal);

      setAuthCookies(reply, accessToken, refreshToken);

      return reply.code(201).send({
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
        user: userRepo.toUser(user),
        workspace: userRepo.toWorkspace(workspace),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(400).send({
        error: "Bad Request",
        message: error.message,
      });
    }
  });

  app.post("/api/v2/auth/refresh", async (request, reply) => {
    try {
      const body = RefreshTokenRequestSchema.parse(request.body) as RefreshTokenRequest;
      const refreshToken = body.refresh_token || request.cookies.refresh_token;

      if (!refreshToken) {
        return reply.code(401).send({
          error: "Unauthorized",
          message: "Refresh token required",
        });
      }

      const principal = await jwtManager.verifyToken(refreshToken);

      const newAccessToken = await jwtManager.createAccessToken(principal);
      const newRefreshToken = await jwtManager.createRefreshToken(principal);

      setAuthCookies(reply, newAccessToken, newRefreshToken);

      return reply.send({
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Invalid or expired refresh token",
      });
    }
  });

  app.post("/api/v2/auth/logout", async (request, reply) => {
    clearAuthCookies(reply);
    return reply.code(204).send();
  });

  app.get("/api/v2/auth/me", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const user = await userRepo.findById(request.principal.user_id);
      if (!user) {
        return reply.code(404).send({
          error: "Not Found",
          message: "User not found",
        });
      }

      const workspaces = await userRepo.getUserWorkspaces(user.id);
      const currentWorkspace = workspaces.find((w) => w.id === request.principal!.workspace_id);

      if (!currentWorkspace) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Workspace not found",
        });
      }

      return reply.send({
        user: userRepo.toUser(user),
        workspace: userRepo.toWorkspace(currentWorkspace),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch user information",
      });
    }
  });
}
