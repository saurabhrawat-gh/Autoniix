import type { FastifyInstance } from "fastify";
import { UserRepository } from "../repositories/user.repository.js";
import { PasswordManager } from "../utils/password.js";

export async function userRoutes(app: FastifyInstance): Promise<void> {
  const userRepo = new UserRepository(app.db);

  // GET /api/v2/users/:user_id - Get user profile
  app.get("/api/v2/users/:user_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { user_id } = request.params as { user_id: string };

      // Users can only fetch themselves or members of their workspace
      if (user_id !== request.principal.user_id) {
        const membership = await userRepo.getWorkspaceMembership(
          user_id,
          request.principal.workspace_id
        );
        if (!membership) {
          return reply.code(403).send({
            error: "Forbidden",
            message: "Cannot access this user",
          });
        }
      }

      const user = await userRepo.findById(user_id);
      if (!user) {
        return reply.code(404).send({
          error: "Not Found",
          message: "User not found",
        });
      }

      return reply.send({
        user: userRepo.toUser(user),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch user",
      });
    }
  });

  // PATCH /api/v2/users/:user_id - Update user profile
  app.patch("/api/v2/users/:user_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { user_id } = request.params as { user_id: string };
      const body = request.body as any;

      // Users can only update themselves
      if (user_id !== request.principal.user_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "You can only update your own profile",
        });
      }

      const user = await userRepo.findById(user_id);
      if (!user) {
        return reply.code(404).send({
          error: "Not Found",
          message: "User not found",
        });
      }

      // If password change requested, verify current password first
      if (body.new_password) {
        if (!body.current_password) {
          return reply.code(400).send({
            error: "Bad Request",
            message: "current_password required to change password",
          });
        }
        const isValid = await PasswordManager.verifyPassword(
          body.current_password,
          user.password_hash
        );
        if (!isValid) {
          return reply.code(401).send({
            error: "Unauthorized",
            message: "Current password is incorrect",
          });
        }
        const newHash = await PasswordManager.hashPassword(body.new_password);
        await app.db`
          UPDATE users SET password_hash = ${newHash}, updated_at = NOW()
          WHERE id = ${user_id}
        `;
      }

      // Update profile fields
      const fullName = body.full_name ?? user.full_name;
      const avatarUrl = body.avatar_url ?? user.avatar_url;

      await app.db`
        UPDATE users
        SET full_name = ${fullName}, avatar_url = ${avatarUrl}, updated_at = NOW()
        WHERE id = ${user_id}
      `;

      const updated = await userRepo.findById(user_id);
      return reply.send({
        user: userRepo.toUser(updated!),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to update user",
      });
    }
  });

  // DELETE /api/v2/users/:user_id - Delete user account
  app.delete("/api/v2/users/:user_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { user_id } = request.params as { user_id: string };

      // Users can only delete themselves
      if (user_id !== request.principal.user_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "You can only delete your own account",
        });
      }

      await app.db`DELETE FROM users WHERE id = ${user_id}`;
      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to delete user",
      });
    }
  });
}
