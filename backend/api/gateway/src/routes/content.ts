import type { FastifyInstance } from "fastify";
import { ContentRepository } from "../repositories/content.repository.js";

export async function contentRoutes(app: FastifyInstance): Promise<void> {
  const contentRepo = new ContentRepository(app.db);

  // GET /api/v2/content - List content with filtering
  app.get("/api/v2/content", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const query = request.query as any;
      const page = parseInt(query.page || "1", 10);
      const pageSize = Math.min(parseInt(query.page_size || "20", 10), 100);

      const { content, total } = await contentRepo.findByWorkspace(request.principal.workspace_id, {
        channelId: query.channel_id,
        status: query.status,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });

      return reply.send({
        content: content.map((c) => contentRepo.toContent(c)),
        pagination: {
          total,
          page,
          page_size: pageSize,
          has_more: total > page * pageSize,
        },
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch content",
      });
    }
  });

  // POST /api/v2/content - Create content
  app.post("/api/v2/content", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const body = request.body as any;

      if (!body.channel_id || typeof body.channel_id !== "string") {
        return reply.code(400).send({
          error: "Bad Request",
          message: "channel_id is required",
        });
      }

      const content = await contentRepo.create({
        workspace_id: request.principal.workspace_id,
        channel_id: body.channel_id,
        title: body.title,
        description: body.description,
        content_type: body.content_type,
        metadata: body.metadata,
      });

      return reply.code(201).send({
        content: contentRepo.toContent(content),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to create content",
      });
    }
  });

  // GET /api/v2/content/:content_id - Get content
  app.get("/api/v2/content/:content_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { content_id } = request.params as { content_id: string };
      const content = await contentRepo.findById(content_id, request.principal.workspace_id);

      if (!content) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Content not found",
        });
      }

      return reply.send({
        content: contentRepo.toContent(content),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch content",
      });
    }
  });

  // PATCH /api/v2/content/:content_id - Update content
  app.patch("/api/v2/content/:content_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { content_id } = request.params as { content_id: string };
      const body = request.body as any;

      const content = await contentRepo.update(content_id, request.principal.workspace_id, {
        title: body.title,
        description: body.description,
        status: body.status,
        content_type: body.content_type,
        duration_seconds: body.duration_seconds,
        thumbnail_url: body.thumbnail_url,
        video_url: body.video_url,
        metadata: body.metadata,
      });

      return reply.send({
        content: contentRepo.toContent(content),
      });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Content not found") {
        return reply.code(404).send({
          error: "Not Found",
          message: "Content not found",
        });
      }
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to update content",
      });
    }
  });

  // DELETE /api/v2/content/:content_id - Delete content
  app.delete("/api/v2/content/:content_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { content_id } = request.params as { content_id: string };
      const content = await contentRepo.findById(content_id, request.principal.workspace_id);

      if (!content) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Content not found",
        });
      }

      await contentRepo.delete(content_id, request.principal.workspace_id);
      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to delete content",
      });
    }
  });
}
