import type { FastifyInstance } from "fastify";
import type { Database } from "../database.js";

/**
 * Workspace deletion cron jobs.
 *
 * Two jobs run periodically:
 * 1. **Warning email**: 48h before a scheduled deletion, send a reminder email
 *    to the workspace owner (idempotent — checks warning_sent_at).
 * 2. **Hard delete**: Permanently delete workspaces that passed their grace
 *    period. Cascades to related tables.
 *
 * Both jobs are safe to run every 5 minutes; they only act on rows where the
 * relevant timestamp threshold has passed.
 */

interface PendingDeletion {
  id: string;
  name: string;
  owner_user_id: string;
  delete_scheduled_at: Date;
  warning_sent_at: Date | null;
}

async function sendDeletionWarnings(db: Database, log: FastifyInstance["log"]): Promise<void> {
  // Find workspaces scheduled for deletion within the next 48 hours
  // that haven't had their warning sent yet.
  const pending = await db<PendingDeletion[]>`
    SELECT id, name, owner_user_id, delete_scheduled_at, warning_sent_at
    FROM workspaces
    WHERE deleted_at IS NOT NULL
      AND delete_scheduled_at IS NOT NULL
      AND delete_scheduled_at <= NOW() + INTERVAL '48 hours'
      AND delete_scheduled_at > NOW()
      AND warning_sent_at IS NULL
  `;

  if (pending.length === 0) return;

  log.info({ count: pending.length }, "Sending workspace deletion warnings");

  for (const workspace of pending) {
    try {
      // TODO: Integrate with email service (SES, SendGrid, etc.)
      // For now, just log and mark as sent.
      log.info(
        {
          workspace_id: workspace.id,
          workspace_name: workspace.name,
          owner_user_id: workspace.owner_user_id,
          delete_scheduled_at: workspace.delete_scheduled_at,
        },
        "Would send deletion warning email"
      );

      await db`
        UPDATE workspaces
        SET warning_sent_at = NOW()
        WHERE id = ${workspace.id}
      `;
    } catch (error) {
      log.error({ error, workspace_id: workspace.id }, "Failed to send deletion warning");
    }
  }
}

async function hardDeleteExpiredWorkspaces(db: Database, log: FastifyInstance["log"]): Promise<void> {
  // Find workspaces past their scheduled deletion time.
  const expired = await db<{ id: string; name: string }[]>`
    SELECT id, name
    FROM workspaces
    WHERE deleted_at IS NOT NULL
      AND delete_scheduled_at IS NOT NULL
      AND delete_scheduled_at <= NOW()
  `;

  if (expired.length === 0) return;

  log.info({ count: expired.length }, "Hard-deleting expired workspaces");

  for (const workspace of expired) {
    try {
      // The cascade is expected to be defined at the DB level via ON DELETE CASCADE.
      // If not, delete related rows here in a transaction.
      await db`DELETE FROM workspaces WHERE id = ${workspace.id}`;
      log.info({ workspace_id: workspace.id, workspace_name: workspace.name }, "Workspace hard-deleted");
    } catch (error) {
      log.error({ error, workspace_id: workspace.id }, "Failed to hard-delete workspace");
    }
  }
}

export function registerWorkspaceDeletionCron(app: FastifyInstance): void {
  const INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

  const runJobs = async () => {
    try {
      await sendDeletionWarnings(app.db, app.log);
      await hardDeleteExpiredWorkspaces(app.db, app.log);
    } catch (error) {
      app.log.error({ error }, "Workspace deletion cron job failed");
    }
  };

  // Run once on startup (after a short delay to let the server settle)
  const startupTimer = setTimeout(runJobs, 10_000);

  // Then run every 5 minutes
  const intervalTimer = setInterval(runJobs, INTERVAL_MS);

  app.addHook("onClose", async () => {
    clearTimeout(startupTimer);
    clearInterval(intervalTimer);
    app.log.info("Workspace deletion cron stopped");
  });

  app.log.info({ interval_seconds: INTERVAL_MS / 1000 }, "Workspace deletion cron registered");
}
