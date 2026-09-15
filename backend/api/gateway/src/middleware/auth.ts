import type { FastifyRequest, FastifyReply } from "fastify";
import type { Principal } from "@autoniix/contracts";

declare module "fastify" {
  interface FastifyRequest {
    principal?: Principal;
  }
}

export async function authMiddleware(request: FastifyRequest, reply: FastifyReply): Promise<void> {
  try {
    const token = extractToken(request);

    if (!token) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Missing authentication token",
      });
    }

    const payload = await request.server.jwt.verify<Principal>(token);
    request.principal = payload;
  } catch (error) {
    return reply.code(401).send({
      error: "Unauthorized",
      message: "Invalid or expired token",
    });
  }
}

function extractToken(request: FastifyRequest): string | null {
  const authHeader = request.headers.authorization;
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }

  const cookieToken = request.cookies.access_token;
  if (cookieToken) {
    return cookieToken;
  }

  return null;
}
