import type { FastifyInstance } from "fastify";
import { UserRepository } from "../repositories/user.repository.js";

export async function workspaceRoutes(app: FastifyInstance): Promise<void> {
  const userRepo = new UserRepository(app.db);

  // GET /api/v2/workspace - Get current workspace
  app.get("/api/v2/workspace", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const workspaces = await userRepo.getUserWorkspaces(request.principal.user_id);
      const workspace = workspaces.find(w => w.id === request.principal!.workspace_id);

      if (!workspace) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Workspace not found",
        });
      }

      return reply.send({
        workspace: userRepo.toWorkspace(workspace),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch workspace",
      });
    }
  });

  // PUT /api/v2/workspace - Update current workspace
  app.put("/api/v2/workspace", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { name } = request.body as { name?: string };

      if (!name || name.trim().length === 0) {
        return reply.code(400).send({
          error: "Bad Request",
          message: "Workspace name is required",
        });
      }

      await app.db`
        UPDATE workspaces
        SET name = ${name}, updated_at = NOW()
        WHERE id = ${request.principal.workspace_id}
      `;

      return reply.send({
        message: "Workspace updated successfully",
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to update workspace",
      });
    }
  });

  // GET /api/v2/workspace/members - List workspace members
  app.get("/api/v2/workspace/members", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const members = await app.db<Array<{
        user_id: string;
        email: string;
        full_name: string;
        role: string;
        joined_at: Date;
      }>>`
        SELECT 
          u.id as user_id,
          u.email,
          u.full_name,
          wm.role,
          wm.created_at as joined_at
        FROM workspace_members wm
        JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ${request.principal.workspace_id}
        ORDER BY wm.created_at ASC
      `;

      return reply.send({
        members: members.map(m => ({
          user_id: m.user_id,
          email: m.email,
          full_name: m.full_name,
          role: m.role,
          joined_at: m.joined_at.toISOString(),
        })),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch members",
      });
    }
  });

  // PUT /api/v2/workspace/members/:user_id/role - Update member role
  app.put("/api/v2/workspace/members/:user_id/role", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { user_id } = request.params as { user_id: string };
      const { role } = request.body as { role: string };

      if (!["owner", "member", "viewer"].includes(role)) {
        return reply.code(400).send({
          error: "Bad Request",
          message: "Invalid role. Must be one of: owner, member, viewer",
        });
      }

      // Check if requester is owner
      const membership = await userRepo.getWorkspaceMembership(
        request.principal.user_id,
        request.principal.workspace_id
      );

      if (!membership || membership.role !== "owner") {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Only workspace owners can change member roles",
        });
      }

      await app.db`
        UPDATE workspace_members
        SET role = ${role}, updated_at = NOW()
        WHERE workspace_id = ${request.principal.workspace_id}
          AND user_id = ${user_id}
      `;

      return reply.send({
        message: "Member role updated successfully",
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to update member role",
      });
    }
  });

  // DELETE /api/v2/workspace/members/:user_id - Remove member
  app.delete("/api/v2/workspace/members/:user_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { user_id } = request.params as { user_id: string };

      // Check if requester is owner
      const membership = await userRepo.getWorkspaceMembership(
        request.principal.user_id,
        request.principal.workspace_id
      );

      if (!membership || membership.role !== "owner") {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Only workspace owners can remove members",
        });
      }

      // Prevent removing the owner
      const targetMembership = await userRepo.getWorkspaceMembership(
        user_id,
        request.principal.workspace_id
      );

      if (targetMembership?.role === "owner") {
        return reply.code(400).send({
          error: "Bad Request",
          message: "Cannot remove workspace owner",
        });
      }

      await app.db`
        DELETE FROM workspace_members
        WHERE workspace_id = ${request.principal.workspace_id}
          AND user_id = ${user_id}
      `;

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to remove member",
      });
    }
  });

  // Stub remaining endpoints
  app.delete("/api/v2/workspaces/:id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented", message: "Workspace deletion (soft-delete with grace period) not yet implemented" });
  });

  app.post("/api/v2/workspaces/:id/cancel-deletion", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.get("/api/v2/workspace/invites", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.post("/api/v2/workspace/invites", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });

  app.delete("/api/v2/workspace/invites/:invite_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    return reply.code(501).send({ error: "Not Implemented" });
  });
}
