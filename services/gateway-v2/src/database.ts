import postgres from "postgres";
import type { Config } from "./config.js";

export type Database = ReturnType<typeof postgres>;

export function createDatabase(config: Config): Database {
  const sql = postgres(config.databaseUrl, {
    max: 20,
    idle_timeout: 20,
    connect_timeout: 10,
    onnotice: () => {},
  });

  return sql;
}

export async function healthCheck(sql: Database): Promise<boolean> {
  try {
    await sql`SELECT 1`;
    return true;
  } catch {
    return false;
  }
}
