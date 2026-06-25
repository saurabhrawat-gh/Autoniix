/// IM-182: Workspace deletion email notifications via Resend API.
///
/// All sends are fire-and-forget (`tokio::spawn`). Failures are logged but
/// never propagate to the caller. An idempotency table
/// (`workspace_deletion_notifications`) prevents double-sends on retries.
use chrono::{DateTime, Utc};
use sqlx::PgPool;

const RESEND_API_URL: &str = "https://api.resend.com/emails";
const BATCH_SIZE: usize = 100;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeletionEmailEvent {
    SoftDelete,
    Warning48h,
    Cancelled,
}

impl DeletionEmailEvent {
    pub fn as_str(self) -> &'static str {
        match self {
            DeletionEmailEvent::SoftDelete => "soft_delete",
            DeletionEmailEvent::Warning48h => "warning_48h",
            DeletionEmailEvent::Cancelled => "cancelled",
        }
    }
}

/// Spawns a background task that sends deletion notification emails to all
/// workspace members. Never blocks the caller.
pub fn fire_workspace_deletion_emails(
    pool: PgPool,
    workspace_id: i64,
    workspace_name: String,
    event: DeletionEmailEvent,
    scheduled_at: Option<DateTime<Utc>>,
) {
    tokio::spawn(async move {
        if let Err(e) =
            send_deletion_emails(&pool, workspace_id, &workspace_name, event, scheduled_at).await
        {
            tracing::warn!(
                workspace_id,
                event = event.as_str(),
                error = ?e,
                "workspace deletion emails failed"
            );
        }
    });
}

async fn send_deletion_emails(
    pool: &PgPool,
    workspace_id: i64,
    workspace_name: &str,
    event: DeletionEmailEvent,
    scheduled_at: Option<DateTime<Utc>>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Idempotency check — skip if we already sent this event.
    let already_sent: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM workspace_deletion_notifications \
         WHERE workspace_id = $1 AND event_type = $2)",
    )
    .bind(workspace_id)
    .bind(event.as_str())
    .fetch_one(pool)
    .await?;

    if already_sent {
        tracing::debug!(
            workspace_id,
            event = event.as_str(),
            "deletion email already sent — skipping"
        );
        return Ok(());
    }

    // Collect member emails.
    let members: Vec<(String,)> = sqlx::query_as(
        "SELECT u.email \
         FROM workspace_members wm \
         JOIN users u ON u.id = wm.user_id \
         WHERE wm.workspace_id = $1 \
         ORDER BY u.id",
    )
    .bind(workspace_id)
    .fetch_all(pool)
    .await?;

    let api_key = std::env::var("RESEND_API_KEY").unwrap_or_default();
    let from = std::env::var("RESEND_FROM_EMAIL")
        .unwrap_or_else(|_| "Autoniix <noreply@autoniix.com>".to_string());

    if api_key.is_empty() {
        tracing::warn!(
            workspace_id,
            "RESEND_API_KEY not set — skipping deletion notification emails"
        );
        return Ok(());
    }

    let client = reqwest::Client::new();
    let (subject, html) = build_email(event, workspace_name, scheduled_at);

    let mut sent_count = 0usize;
    for (i, chunk) in members.chunks(BATCH_SIZE).enumerate() {
        if i > 0 {
            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
        }
        for (email,) in chunk {
            let payload = serde_json::json!({
                "from": from,
                "to": [email],
                "subject": subject,
                "html": html,
            });
            match client
                .post(RESEND_API_URL)
                .bearer_auth(&api_key)
                .json(&payload)
                .send()
                .await
            {
                Ok(resp) if resp.status().is_success() => {
                    sent_count += 1;
                }
                Ok(resp) => {
                    tracing::warn!(
                        workspace_id,
                        event = event.as_str(),
                        email = email.as_str(),
                        status = resp.status().as_u16(),
                        "resend rejected deletion email"
                    );
                }
                Err(e) => {
                    tracing::warn!(
                        workspace_id,
                        event = event.as_str(),
                        email = email.as_str(),
                        error = ?e,
                        "resend request error for deletion email"
                    );
                }
            }
        }
    }

    // Record the send so retries are idempotent.
    sqlx::query(
        "INSERT INTO workspace_deletion_notifications (workspace_id, event_type) \
         VALUES ($1, $2) \
         ON CONFLICT (workspace_id, event_type) DO NOTHING",
    )
    .bind(workspace_id)
    .bind(event.as_str())
    .execute(pool)
    .await?;

    tracing::info!(
        workspace_id,
        event = event.as_str(),
        sent = sent_count,
        total = members.len(),
        "workspace deletion notification emails dispatched"
    );

    Ok(())
}

fn build_email(
    event: DeletionEmailEvent,
    workspace_name: &str,
    scheduled_at: Option<DateTime<Utc>>,
) -> (String, String) {
    match event {
        DeletionEmailEvent::SoftDelete => {
            let subject = format!("Your workspace \"{workspace_name}\" is scheduled for deletion");
            let scheduled_str = scheduled_at
                .map(|d| d.format("%B %d, %Y at %H:%M UTC").to_string())
                .unwrap_or_else(|| "7 days from now".to_string());
            let html = wrap(
                &subject,
                &format!(
                    "<h2>Workspace deletion initiated</h2>\
                     <p>The workspace <strong>{workspace_name}</strong> has been scheduled for \
                     permanent deletion on <strong>{scheduled_str}</strong>.</p>\
                     <p>If this was a mistake the workspace owner can cancel the deletion from \
                     workspace settings before the deadline.</p>\
                     <p style=\"color:#6b7280;font-size:13px\">All workspace data — channels, \
                     content, settings, and member access — will be permanently removed.</p>"
                ),
            );
            (subject, html)
        }
        DeletionEmailEvent::Warning48h => {
            let subject =
                format!("⚠️ Final warning: \"{workspace_name}\" will be deleted in 48 hours");
            let html = wrap(
                &subject,
                &format!(
                    "<h2 style=\"color:#dc2626\">48-hour deletion warning</h2>\
                     <p>This is a final reminder that the workspace \
                     <strong>{workspace_name}</strong> is scheduled for permanent deletion \
                     <strong>in approximately 48 hours</strong>.</p>\
                     <p>If the owner does not cancel the deletion in time, all workspace data \
                     will be permanently removed and cannot be recovered.</p>"
                ),
            );
            (subject, html)
        }
        DeletionEmailEvent::Cancelled => {
            let subject = format!("Deletion of \"{workspace_name}\" has been cancelled");
            let html = wrap(
                &subject,
                &format!(
                    "<h2 style=\"color:#10b981\">Workspace deletion cancelled</h2>\
                     <p>The scheduled deletion of <strong>{workspace_name}</strong> has been \
                     cancelled. Your workspace and all its data remain intact.</p>"
                ),
            );
            (subject, html)
        }
    }
}

fn wrap(title: &str, body: &str) -> String {
    format!(
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">\
         <title>{title}</title></head>\
         <body style=\"font-family:sans-serif;color:#111;max-width:560px;margin:32px auto;padding:0 16px\">\
         {body}\
         <hr style=\"margin:32px 0;border:none;border-top:1px solid #e5e7eb\">\
         <p style=\"color:#6b7280;font-size:12px\">Autoniix — automated YouTube content platform</p>\
         </body></html>"
    )
}
