import type { FastifyInstance } from "fastify";
import type { Principal } from "@autoniix/contracts";

export interface JwtClaims extends Principal {
  iat: number;
  exp: number;
}

export class JwtManager {
  constructor(private app: FastifyInstance) {}

  async createAccessToken(principal: Principal): Promise<string> {
    return this.app.jwt.sign(principal, {
      expiresIn: "1h",
    });
  }

  async createRefreshToken(principal: Principal): Promise<string> {
    return this.app.jwt.sign(principal, {
      expiresIn: "30d",
    });
  }

  async verifyToken(token: string): Promise<Principal> {
    try {
      const decoded = await this.app.jwt.verify<JwtClaims>(token);
      return {
        user_id: decoded.user_id,
        workspace_id: decoded.workspace_id,
        email: decoded.email,
        roles: decoded.roles,
        global_roles: decoded.global_roles,
        permissions: decoded.permissions,
      };
    } catch (error) {
      throw new Error("Invalid or expired token");
    }
  }
}
