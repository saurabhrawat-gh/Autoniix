import type { Database } from "../database.js";

export interface ContentRow {
  content_id: string;
  workspace_id: string;
  channel_id: string;
  title: string | null;
  description: string | null;
  status: string;
  content_type: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  video_url: string | null;
  metadata: any;
  created_at: Date;
  updated_at: Date;
  published_at: Date | null;
}

export interface CreateContentInput {
  workspace_id: string;
  channel_id: string;
  title?: string;
  description?: string;
  content_type?: string;
  metadata?: any;
}

export interface UpdateContentInput {
  title?: string;
  description?: string;
  status?: string;
  content_type?: string;
  duration_seconds?: number;
  thumbnail_url?: string;
  video_url?: string;
  metadata?: any;
}

export class ContentRepository {
  constructor(private db: Database) {}

  async findByWorkspace(
    workspaceId: string,
    options: {
      channelId?: string;
      status?: string;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<{ content: ContentRow[]; total: number }> {
    const { channelId, status, limit = 20, offset = 0 } = options;

    const channelFilter = channelId
      ? this.db`AND channel_id = ${channelId}`
      : this.db``;
    const statusFilter = status
      ? this.db`AND status = ${status}`
      : this.db``;

    const content = await this.db<ContentRow[]>`
      SELECT content_id, workspace_id, channel_id, title, description,
             status, content_type, duration_seconds, thumbnail_url, video_url,
             metadata, created_at, updated_at, published_at
      FROM videos
      WHERE workspace_id = ${workspaceId}
      ${channelFilter}
      ${statusFilter}
      ORDER BY created_at DESC
      LIMIT ${limit}
      OFFSET ${offset}
    `;

    const [{ count }] = await this.db<[{ count: string }]>`
      SELECT COUNT(*)::text as count
      FROM videos
      WHERE workspace_id = ${workspaceId}
      ${channelFilter}
      ${statusFilter}
    `;

    return {
      content,
      total: parseInt(count, 10),
    };
  }

  async findById(
    contentId: string,
    workspaceId: string
  ): Promise<ContentRow | null> {
    const [content] = await this.db<ContentRow[]>`
      SELECT content_id, workspace_id, channel_id, title, description,
             status, content_type, duration_seconds, thumbnail_url, video_url,
             metadata, created_at, updated_at, published_at
      FROM videos
      WHERE content_id = ${contentId} AND workspace_id = ${workspaceId}
      LIMIT 1
    `;
    return content || null;
  }

  async create(input: CreateContentInput): Promise<ContentRow> {
    const [content] = await this.db<ContentRow[]>`
      INSERT INTO videos (
        workspace_id, channel_id, title, description,
        status, content_type, metadata
      )
      VALUES (
        ${input.workspace_id},
        ${input.channel_id},
        ${input.title || null},
        ${input.description || null},
        'draft',
        ${input.content_type || null},
        ${JSON.stringify(input.metadata || {})}
      )
      RETURNING content_id, workspace_id, channel_id, title, description,
                status, content_type, duration_seconds, thumbnail_url, video_url,
                metadata, created_at, updated_at, published_at
    `;
    if (!content) throw new Error("Failed to create content");
    return content;
  }

  async update(
    contentId: string,
    workspaceId: string,
    input: UpdateContentInput
  ): Promise<ContentRow> {
    const existing = await this.findById(contentId, workspaceId);
    if (!existing) throw new Error("Content not found");

    const [content] = await this.db<ContentRow[]>`
      UPDATE videos
      SET
        title = ${input.title ?? existing.title},
        description = ${input.description ?? existing.description},
        status = ${input.status ?? existing.status},
        content_type = ${input.content_type ?? existing.content_type},
        duration_seconds = ${input.duration_seconds ?? existing.duration_seconds},
        thumbnail_url = ${input.thumbnail_url ?? existing.thumbnail_url},
        video_url = ${input.video_url ?? existing.video_url},
        metadata = ${input.metadata ? JSON.stringify(input.metadata) : JSON.stringify(existing.metadata)},
        updated_at = NOW()
      WHERE content_id = ${contentId} AND workspace_id = ${workspaceId}
      RETURNING content_id, workspace_id, channel_id, title, description,
                status, content_type, duration_seconds, thumbnail_url, video_url,
                metadata, created_at, updated_at, published_at
    `;
    if (!content) throw new Error("Content not found");
    return content;
  }

  async delete(contentId: string, workspaceId: string): Promise<void> {
    await this.db`
      DELETE FROM videos
      WHERE content_id = ${contentId} AND workspace_id = ${workspaceId}
    `;
  }

  toContent(row: ContentRow) {
    return {
      content_id: row.content_id,
      workspace_id: row.workspace_id,
      channel_id: row.channel_id,
      title: row.title,
      description: row.description,
      status: row.status,
      content_type: row.content_type,
      duration_seconds: row.duration_seconds,
      thumbnail_url: row.thumbnail_url,
      video_url: row.video_url,
      metadata: row.metadata,
      created_at: row.created_at.toISOString(),
      updated_at: row.updated_at.toISOString(),
      published_at: row.published_at?.toISOString() || null,
    };
  }
}
