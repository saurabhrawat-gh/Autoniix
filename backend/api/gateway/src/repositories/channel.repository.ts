import type { Database } from "../database.js";

export interface ChannelRow {
  channel_id: string;
  workspace_id: string;
  channel_name: string;
  niche: string | null;
  sub_niche: string | null;
  platform: string;
  status: string;
  handle: string | null;
  description: string | null;
  tone: string | null;
  brand_personality: string | null;
  auto_upload: boolean;
  human_review_required: boolean;
  content_type_tags: string[] | null;
  created_at: Date;
  updated_at: Date;
}

export interface CreateChannelInput {
  workspace_id: string;
  channel_name: string;
  niche?: string;
  sub_niche?: string;
  platform?: string;
  handle?: string;
  description?: string;
  tone?: string;
  brand_personality?: string;
  auto_upload?: boolean;
  human_review_required?: boolean;
  content_type_tags?: string[];
}

export interface UpdateChannelInput {
  channel_name?: string;
  niche?: string;
  sub_niche?: string;
  handle?: string;
  description?: string;
  tone?: string;
  brand_personality?: string;
  auto_upload?: boolean;
  human_review_required?: boolean;
  content_type_tags?: string[];
}

export class ChannelRepository {
  constructor(private db: Database) {}

  async findByWorkspace(
    workspaceId: string,
    options: {
      status?: string;
      includeArchived?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<{ channels: ChannelRow[]; total: number }> {
    const { status, includeArchived = false, limit = 50, offset = 0 } = options;

    const statusFilter = status
      ? this.db`AND status = ${status}`
      : includeArchived
        ? this.db``
        : this.db`AND status != 'archived'`;

    const channels = await this.db<ChannelRow[]>`
      SELECT channel_id, workspace_id, channel_name, niche, sub_niche,
             platform, status, handle, description, tone, brand_personality,
             auto_upload, human_review_required, content_type_tags,
             created_at, updated_at
      FROM channels
      WHERE workspace_id = ${workspaceId}
      ${statusFilter}
      ORDER BY created_at DESC
      LIMIT ${limit}
      OFFSET ${offset}
    `;

    const [{ count }] = await this.db<[{ count: string }]>`
      SELECT COUNT(*)::text as count
      FROM channels
      WHERE workspace_id = ${workspaceId}
      ${statusFilter}
    `;

    return {
      channels,
      total: parseInt(count, 10),
    };
  }

  async findById(channelId: string, workspaceId: string): Promise<ChannelRow | null> {
    const [channel] = await this.db<ChannelRow[]>`
      SELECT channel_id, workspace_id, channel_name, niche, sub_niche,
             platform, status, handle, description, tone, brand_personality,
             auto_upload, human_review_required, content_type_tags,
             created_at, updated_at
      FROM channels
      WHERE channel_id = ${channelId} AND workspace_id = ${workspaceId}
      LIMIT 1
    `;
    return channel || null;
  }

  async create(input: CreateChannelInput): Promise<ChannelRow> {
    const [channel] = await this.db<ChannelRow[]>`
      INSERT INTO channels (
        workspace_id, channel_name, niche, sub_niche, platform,
        status, handle, description, tone, brand_personality,
        auto_upload, human_review_required, content_type_tags
      )
      VALUES (
        ${input.workspace_id},
        ${input.channel_name},
        ${input.niche || null},
        ${input.sub_niche || null},
        ${input.platform || "youtube"},
        'active',
        ${input.handle || null},
        ${input.description || null},
        ${input.tone || null},
        ${input.brand_personality || null},
        ${input.auto_upload ?? false},
        ${input.human_review_required ?? true},
        ${input.content_type_tags || null}
      )
      RETURNING channel_id, workspace_id, channel_name, niche, sub_niche,
                platform, status, handle, description, tone, brand_personality,
                auto_upload, human_review_required, content_type_tags,
                created_at, updated_at
    `;
    if (!channel) throw new Error("Failed to create channel");
    return channel;
  }

  async update(channelId: string, workspaceId: string, input: UpdateChannelInput): Promise<ChannelRow> {
    const existing = await this.findById(channelId, workspaceId);
    if (!existing) throw new Error("Channel not found");

    const [channel] = await this.db<ChannelRow[]>`
      UPDATE channels
      SET
        channel_name = ${input.channel_name ?? existing.channel_name},
        niche = ${input.niche ?? existing.niche},
        sub_niche = ${input.sub_niche ?? existing.sub_niche},
        handle = ${input.handle ?? existing.handle},
        description = ${input.description ?? existing.description},
        tone = ${input.tone ?? existing.tone},
        brand_personality = ${input.brand_personality ?? existing.brand_personality},
        auto_upload = ${input.auto_upload ?? existing.auto_upload},
        human_review_required = ${input.human_review_required ?? existing.human_review_required},
        content_type_tags = ${input.content_type_tags ?? existing.content_type_tags},
        updated_at = NOW()
      WHERE channel_id = ${channelId} AND workspace_id = ${workspaceId}
      RETURNING channel_id, workspace_id, channel_name, niche, sub_niche,
                platform, status, handle, description, tone, brand_personality,
                auto_upload, human_review_required, content_type_tags,
                created_at, updated_at
    `;
    if (!channel) throw new Error("Channel not found");
    return channel;
  }

  async updateStatus(
    channelId: string,
    workspaceId: string,
    status: "active" | "disabled" | "archived"
  ): Promise<ChannelRow> {
    const [channel] = await this.db<ChannelRow[]>`
      UPDATE channels
      SET status = ${status}, updated_at = NOW()
      WHERE channel_id = ${channelId} AND workspace_id = ${workspaceId}
      RETURNING channel_id, workspace_id, channel_name, niche, sub_niche,
                platform, status, handle, description, tone, brand_personality,
                auto_upload, human_review_required, content_type_tags,
                created_at, updated_at
    `;
    if (!channel) throw new Error("Channel not found");
    return channel;
  }

  async delete(channelId: string, workspaceId: string): Promise<void> {
    await this.db`
      DELETE FROM channels
      WHERE channel_id = ${channelId} AND workspace_id = ${workspaceId}
    `;
  }

  async getStats(workspaceId: string): Promise<{
    total: number;
    active: number;
    disabled: number;
    archived: number;
  }> {
    const [stats] = await this.db<
      [
        {
          total: string;
          active: string;
          disabled: string;
          archived: string;
        },
      ]
    >`
      SELECT
        COUNT(*)::text AS total,
        COUNT(*) FILTER (WHERE status = 'active')::text AS active,
        COUNT(*) FILTER (WHERE status = 'disabled')::text AS disabled,
        COUNT(*) FILTER (WHERE status = 'archived')::text AS archived
      FROM channels
      WHERE workspace_id = ${workspaceId}
    `;

    return {
      total: parseInt(stats?.total || "0", 10),
      active: parseInt(stats?.active || "0", 10),
      disabled: parseInt(stats?.disabled || "0", 10),
      archived: parseInt(stats?.archived || "0", 10),
    };
  }

  toChannel(row: ChannelRow) {
    return {
      channel_id: row.channel_id,
      workspace_id: row.workspace_id,
      channel_name: row.channel_name,
      niche: row.niche,
      sub_niche: row.sub_niche,
      platform: row.platform,
      status: row.status,
      handle: row.handle,
      description: row.description,
      tone: row.tone,
      brand_personality: row.brand_personality,
      auto_upload: row.auto_upload,
      human_review_required: row.human_review_required,
      content_type_tags: row.content_type_tags || [],
      created_at: row.created_at.toISOString(),
      updated_at: row.updated_at.toISOString(),
    };
  }
}
