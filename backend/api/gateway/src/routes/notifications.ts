import type { FastifyInstance } from "fastify";

interface NotificationRow {
  id: string;
  user_id: string;
  workspace_id: string;
  type: string;
  title: string;
  message: string;
  data: any;
  read_at: Date | null;
  created_at: Date;
}

export async function notificationRoutes(app: FastifyInstance): Promise<void> {
  // GET /api/v2/notifications - List user's notifications
  app.get("/api/v2/notifications", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const query = request.query as any;
      const page = parseInt(query.page || "1", 10);
      const pageSize = Math.min(parseInt(query.page_size || "20", 10), 100);
      const unreadOnly = query.unread_only === "true";

      const readFilter = unreadOnly ? app.db`AND read_at IS NULL` : app.db``;

      const notifications = await app.db<NotificationRow[]>`
        SELECT id, user_id, workspace_id, type, title, message, data,
               read_at, created_at
        FROM notifications
        WHERE user_id = ${request.principal.user_id}
          AND workspace_id = ${request.principal.workspace_id}
          ${readFilter}
        ORDER BY created_at DESC
        LIMIT ${pageSize}
        OFFSET ${(page - 1) * pageSize}
      `;

      const [{ count }] = await app.db<[{ count: string }]>`
        SELECT COUNT(*)::text as count
        FROM notifications
        WHERE user_id = ${request.principal.user_id}
          AND workspace_id = ${request.principal.workspace_id}
          ${readFilter}
      `;

      const [{ unread_count }] = await app.db<[{ unread_count: string }]>`
        SELECT COUNT(*)::text as unread_count
        FROM notifications
        WHERE user_id = ${request.principal.user_id}
          AND workspace_id = ${request.principal.workspace_id}
          AND read_at IS NULL
      `;

      return reply.send({
        notifications: notifications.map((n) => ({
          id: n.id,
          type: n.type,
          title: n.title,
          message: n.message,
          data: n.data,
          read: n.read_at !== null,
          read_at: n.read_at?.toISOString() || null,
          created_at: n.created_at.toISOString(),
        })),
        pagination: {
          total: parseInt(count, 10),
          page,
          page_size: pageSize,
          has_more: parseInt(count, 10) > page * pageSize,
        },
        unread_count: parseInt(unread_count, 10),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch notifications",
      });
    }
  });

  // PATCH /api/v2/notifications/:id/read - Mark notification as read
  app.patch("/api/v2/notifications/:id/read", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { id } = request.params as { id: string };

      const result = await app.db`
        UPDATE notifications
        SET read_at = NOW()
        WHERE id = ${id}
          AND user_id = ${request.principal.user_id}
          AND read_at IS NULL
      `;

      if (result.count === 0) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Notification not found or already read",
        });
      }

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to mark notification as read",
      });
    }
  });

  // POST /api/v2/notifications/mark-all-read - Mark all as read
  app.post("/api/v2/notifications/mark-all-read", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const result = await app.db`
        UPDATE notifications
        SET read_at = NOW()
        WHERE user_id = ${request.principal.user_id}
          AND workspace_id = ${request.principal.workspace_id}
          AND read_at IS NULL
      `;

      return reply.send({
        updated_count: result.count,
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to mark notifications as read",
      });
    }
  });
}
