import type { FastifyInstance } from "fastify";
import { ChannelRepository } from "../repositories/channel.repository.js";

export async function channelRoutes(app: FastifyInstance): Promise<void> {
  const channelRepo = new ChannelRepository(app.db);

  // GET /api/v2/channels/stats - Channel stats (must come before /:id)
  app.get("/api/v2/channels/stats", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }
    try {
      const stats = await channelRepo.getStats(request.principal.workspace_id);
      return reply.send({ stats });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch channel stats",
      });
    }
  });

  // GET /api/v2/channels - List channels
  app.get("/api/v2/channels", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const query = request.query as any;
      const page = parseInt(query.page || "1", 10);
      const pageSize = Math.min(parseInt(query.page_size || "20", 10), 100);
      const status = query.status;
      const includeArchived = query.include_archived === "true";

      const { channels, total } = await channelRepo.findByWorkspace(
        request.principal.workspace_id,
        {
          status,
          includeArchived,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        }
      );

      return reply.send({
        channels: channels.map((c) => channelRepo.toChannel(c)),
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
        message: "Failed to fetch channels",
      });
    }
  });

  // POST /api/v2/channels - Create channel
  app.post("/api/v2/channels", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const body = request.body as any;

      if (!body.channel_name || typeof body.channel_name !== "string") {
        return reply.code(400).send({
          error: "Bad Request",
          message: "channel_name is required",
        });
      }

      const channel = await channelRepo.create({
        workspace_id: request.principal.workspace_id,
        channel_name: body.channel_name,
        niche: body.niche,
        sub_niche: body.sub_niche,
        platform: body.platform || "youtube",
        handle: body.handle,
        description: body.description,
        tone: body.tone,
        brand_personality: body.brand_personality,
        auto_upload: body.auto_upload,
        human_review_required: body.human_review_required,
        content_type_tags: body.content_type_tags,
      });

      return reply.code(201).send({
        channel: channelRepo.toChannel(channel),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to create channel",
      });
    }
  });

  // GET /api/v2/channels/:channel_id - Get channel
  app.get("/api/v2/channels/:channel_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.findById(
        channel_id,
        request.principal.workspace_id
      );

      if (!channel) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Channel not found",
        });
      }

      return reply.send({
        channel: channelRepo.toChannel(channel),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch channel",
      });
    }
  });

  // PUT /api/v2/channels/:channel_id - Update channel
  app.put("/api/v2/channels/:channel_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const body = request.body as any;

      const channel = await channelRepo.update(
        channel_id,
        request.principal.workspace_id,
        {
          channel_name: body.channel_name,
          niche: body.niche,
          sub_niche: body.sub_niche,
          handle: body.handle,
          description: body.description,
          tone: body.tone,
          brand_personality: body.brand_personality,
          auto_upload: body.auto_upload,
          human_review_required: body.human_review_required,
          content_type_tags: body.content_type_tags,
        }
      );

      return reply.send({
        channel: channelRepo.toChannel(channel),
      });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Channel not found") {
        return reply.code(404).send({
          error: "Not Found",
          message: "Channel not found",
        });
      }
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to update channel",
      });
    }
  });

  // DELETE /api/v2/channels/:channel_id - Delete channel
  app.delete("/api/v2/channels/:channel_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.findById(
        channel_id,
        request.principal.workspace_id
      );

      if (!channel) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Channel not found",
        });
      }

      await channelRepo.delete(channel_id, request.principal.workspace_id);
      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to delete channel",
      });
    }
  });

  // PUT /api/v2/channels/:channel_id/enable - Enable channel
  app.put("/api/v2/channels/:channel_id/enable", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.updateStatus(
        channel_id,
        request.principal.workspace_id,
        "active"
      );
      return reply.send({ channel: channelRepo.toChannel(channel) });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Channel not found") {
        return reply.code(404).send({ error: "Not Found" });
      }
      return reply.code(500).send({ error: "Internal Server Error" });
    }
  });

  // PUT /api/v2/channels/:channel_id/disable - Disable channel
  app.put("/api/v2/channels/:channel_id/disable", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.updateStatus(
        channel_id,
        request.principal.workspace_id,
        "disabled"
      );
      return reply.send({ channel: channelRepo.toChannel(channel) });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Channel not found") {
        return reply.code(404).send({ error: "Not Found" });
      }
      return reply.code(500).send({ error: "Internal Server Error" });
    }
  });

  // PUT /api/v2/channels/:channel_id/archive - Archive channel
  app.put("/api/v2/channels/:channel_id/archive", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.updateStatus(
        channel_id,
        request.principal.workspace_id,
        "archived"
      );
      return reply.send({ channel: channelRepo.toChannel(channel) });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Channel not found") {
        return reply.code(404).send({ error: "Not Found" });
      }
      return reply.code(500).send({ error: "Internal Server Error" });
    }
  });

  // PUT /api/v2/channels/:channel_id/restore - Restore archived channel
  app.put("/api/v2/channels/:channel_id/restore", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({ error: "Unauthorized" });
    }

    try {
      const { channel_id } = request.params as { channel_id: string };
      const channel = await channelRepo.updateStatus(
        channel_id,
        request.principal.workspace_id,
        "active"
      );
      return reply.send({ channel: channelRepo.toChannel(channel) });
    } catch (error: any) {
      request.log.error(error);
      if (error.message === "Channel not found") {
        return reply.code(404).send({ error: "Not Found" });
      }
      return reply.code(500).send({ error: "Internal Server Error" });
    }
  });
}
