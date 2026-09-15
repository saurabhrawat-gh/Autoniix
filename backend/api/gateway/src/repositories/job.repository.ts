import type { Database } from "../database.js";
import type { Job, JobConfig, JobProgress, JobStatus } from "@autoniix/contracts";

export interface JobRow {
  id: string;
  workspace_id: string;
  channel_id: string;
  status: string;
  config: any;
  progress: any;
  created_at: Date;
  updated_at: Date;
  completed_at: Date | null;
  error_message: string | null;
}

export class JobRepository {
  constructor(private db: Database) {}

  async findById(jobId: string): Promise<JobRow | null> {
    const [job] = await this.db<JobRow[]>`
      SELECT id, workspace_id, channel_id, status, config, progress,
             created_at, updated_at, completed_at, error_message
      FROM jobs
      WHERE id = ${jobId}
      LIMIT 1
    `;
    return job || null;
  }

  async findByWorkspace(
    workspaceId: string,
    options: {
      statusFilter?: string[];
      sortBy?: string;
      sortDesc?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<{ jobs: JobRow[]; total: number }> {
    const { statusFilter, sortBy = "created_at", sortDesc = true, limit = 20, offset = 0 } = options;

    const statusCondition = statusFilter?.length ? this.db`AND status = ANY(${statusFilter})` : this.db``;

    const orderDirection = sortDesc ? this.db`DESC` : this.db`ASC`;

    const jobs = await this.db<JobRow[]>`
      SELECT id, workspace_id, channel_id, status, config, progress,
             created_at, updated_at, completed_at, error_message
      FROM jobs
      WHERE workspace_id = ${workspaceId}
      ${statusCondition}
      ORDER BY ${this.db(sortBy)} ${orderDirection}
      LIMIT ${limit}
      OFFSET ${offset}
    `;

    const [{ count }] = await this.db<[{ count: string }]>`
      SELECT COUNT(*)::text as count
      FROM jobs
      WHERE workspace_id = ${workspaceId}
      ${statusCondition}
    `;

    return {
      jobs,
      total: parseInt(count, 10),
    };
  }

  async create(workspaceId: string, channelId: string, config: JobConfig): Promise<JobRow> {
    const [job] = await this.db<JobRow[]>`
      INSERT INTO jobs (workspace_id, channel_id, status, config)
      VALUES (${workspaceId}, ${channelId}, 'pending', ${JSON.stringify(config)})
      RETURNING id, workspace_id, channel_id, status, config, progress,
                created_at, updated_at, completed_at, error_message
    `;
    if (!job) throw new Error("Failed to create job");
    return job;
  }

  async update(jobId: string, config: JobConfig): Promise<JobRow> {
    const [job] = await this.db<JobRow[]>`
      UPDATE jobs
      SET config = ${JSON.stringify(config)},
          updated_at = NOW()
      WHERE id = ${jobId}
      RETURNING id, workspace_id, channel_id, status, config, progress,
                created_at, updated_at, completed_at, error_message
    `;
    if (!job) throw new Error("Job not found");
    return job;
  }

  async updateStatus(jobId: string, status: JobStatus, errorMessage?: string): Promise<JobRow> {
    const completedAt = status === "completed" || status === "failed" ? this.db`NOW()` : this.db`NULL`;

    const [job] = await this.db<JobRow[]>`
      UPDATE jobs
      SET status = ${status},
          error_message = ${errorMessage || null},
          completed_at = ${completedAt},
          updated_at = NOW()
      WHERE id = ${jobId}
      RETURNING id, workspace_id, channel_id, status, config, progress,
                created_at, updated_at, completed_at, error_message
    `;
    if (!job) throw new Error("Job not found");
    return job;
  }

  async delete(jobId: string): Promise<void> {
    await this.db`
      DELETE FROM jobs
      WHERE id = ${jobId}
    `;
  }

  toJob(row: JobRow): Job {
    return {
      id: row.id,
      workspace_id: row.workspace_id,
      channel_id: row.channel_id,
      status: row.status as JobStatus,
      config: row.config as JobConfig,
      progress: row.progress as JobProgress | null,
      created_at: row.created_at.toISOString(),
      updated_at: row.updated_at.toISOString(),
      completed_at: row.completed_at?.toISOString() || null,
      error_message: row.error_message,
    };
  }
}
