import type { Database } from "../database.js";
import type { User, Workspace } from "@autoniix/contracts";

export interface UserRow {
  id: string;
  email: string;
  password_hash: string;
  full_name: string;
  avatar_url: string | null;
  created_at: Date;
}

export interface WorkspaceRow {
  id: string;
  name: string;
  owner_id: string;
  created_at: Date;
}

export interface WorkspaceMemberRow {
  workspace_id: string;
  user_id: string;
  role: string;
}

export class UserRepository {
  constructor(private db: Database) {}

  async findByEmail(email: string): Promise<UserRow | null> {
    const [user] = await this.db<UserRow[]>`
      SELECT id, email, password_hash, full_name, avatar_url, created_at
      FROM users
      WHERE email = ${email}
      LIMIT 1
    `;
    return user || null;
  }

  async findById(id: string): Promise<UserRow | null> {
    const [user] = await this.db<UserRow[]>`
      SELECT id, email, password_hash, full_name, avatar_url, created_at
      FROM users
      WHERE id = ${id}
      LIMIT 1
    `;
    return user || null;
  }

  async create(email: string, passwordHash: string, fullName: string): Promise<UserRow> {
    const [user] = await this.db<UserRow[]>`
      INSERT INTO users (email, password_hash, full_name)
      VALUES (${email}, ${passwordHash}, ${fullName})
      RETURNING id, email, password_hash, full_name, avatar_url, created_at
    `;
    if (!user) throw new Error("Failed to create user");
    return user;
  }

  async getUserWorkspaces(userId: string): Promise<WorkspaceRow[]> {
    return await this.db<WorkspaceRow[]>`
      SELECT w.id, w.name, w.owner_id, w.created_at
      FROM workspaces w
      INNER JOIN workspace_members wm ON w.id = wm.workspace_id
      WHERE wm.user_id = ${userId}
      ORDER BY w.created_at DESC
    `;
  }

  async getWorkspaceMembership(userId: string, workspaceId: string): Promise<WorkspaceMemberRow | null> {
    const [member] = await this.db<WorkspaceMemberRow[]>`
      SELECT workspace_id, user_id, role
      FROM workspace_members
      WHERE user_id = ${userId} AND workspace_id = ${workspaceId}
      LIMIT 1
    `;
    return member || null;
  }

  async createWorkspace(name: string, ownerId: string): Promise<WorkspaceRow> {
    const [workspace] = await this.db<WorkspaceRow[]>`
      INSERT INTO workspaces (name, owner_id)
      VALUES (${name}, ${ownerId})
      RETURNING id, name, owner_id, created_at
    `;

    if (!workspace) throw new Error("Failed to create workspace");

    await this.db`
      INSERT INTO workspace_members (workspace_id, user_id, role)
      VALUES (${workspace.id}, ${ownerId}, 'owner')
    `;

    return workspace;
  }

  toUser(row: UserRow): User {
    return {
      id: row.id,
      email: row.email,
      full_name: row.full_name,
      avatar_url: row.avatar_url,
      roles: [],
      created_at: row.created_at.toISOString(),
    };
  }

  toWorkspace(row: WorkspaceRow): Workspace {
    return {
      id: row.id,
      name: row.name,
      owner_id: row.owner_id,
      created_at: row.created_at.toISOString(),
    };
  }
}
