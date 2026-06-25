use anyhow::Result;
use std::net::SocketAddr;
use tracing::info;

use gateway::{create_app, create_pool, Config};

mod observability;

/// Polls every hour for workspaces whose `delete_scheduled_at` is between
/// 47 and 48 hours away and sends a final-warning email to all members.
async fn deletion_warning_cron(pool: sqlx::PgPool) {
    use gateway::email::{fire_workspace_deletion_emails, DeletionEmailEvent};
    use tokio::time::{interval, Duration};

    let mut ticker = interval(Duration::from_secs(3600));
    loop {
        ticker.tick().await;
        let rows: Vec<(i64, String, chrono::DateTime<chrono::Utc>)> = match sqlx::query_as(
            "SELECT id, name, delete_scheduled_at \
             FROM workspaces \
             WHERE deleted_at IS NOT NULL \
               AND delete_scheduled_at IS NOT NULL \
               AND delete_scheduled_at > NOW() + INTERVAL '47 hours' \
               AND delete_scheduled_at <= NOW() + INTERVAL '48 hours' \
               AND status = 'pending_deletion'",
        )
        .fetch_all(&pool)
        .await
        {
            Ok(r) => r,
            Err(e) => {
                tracing::warn!("deletion_warning_cron: query failed: {:?}", e);
                continue;
            }
        };

        for (workspace_id, name, scheduled_at) in rows {
            tracing::info!(
                workspace_id,
                "deletion_warning_cron: sending 48h warning emails"
            );
            fire_workspace_deletion_emails(
                pool.clone(),
                workspace_id,
                name,
                DeletionEmailEvent::Warning48h,
                Some(scheduled_at),
            );
        }
    }
}

/// Polls every hour for workspaces whose grace period has expired and
/// performs a full FK-safe cascade delete on each one.
async fn hard_delete_cron(pool: sqlx::PgPool) {
    use gateway::routes::workspace::hard_delete_workspace;
    use tokio::time::{interval, Duration};

    let mut ticker = interval(Duration::from_secs(3600));
    loop {
        ticker.tick().await;
        let expired: Vec<(i64,)> = match sqlx::query_as(
            "SELECT id FROM workspaces \
             WHERE deleted_at IS NOT NULL \
               AND delete_scheduled_at IS NOT NULL \
               AND delete_scheduled_at <= NOW() \
               AND status = 'pending_deletion'",
        )
        .fetch_all(&pool)
        .await
        {
            Ok(rows) => rows,
            Err(e) => {
                tracing::warn!("hard_delete_cron: query failed: {:?}", e);
                continue;
            }
        };

        for (workspace_id,) in expired {
            tracing::info!(
                workspace_id,
                "hard_delete_cron: grace period expired, deleting"
            );
            hard_delete_workspace(&pool, workspace_id).await;
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();

    observability::init_tracing()?;

    let config = Config::from_env()?;
    info!("Starting Autoniix Gateway v{}", env!("CARGO_PKG_VERSION"));
    info!("Environment: {}", config.environment);

    let pool = create_pool(&config.database_url).await?;
    info!("Database connection established");

    tokio::spawn(hard_delete_cron(pool.clone()));
    info!("Workspace hard-delete cron task started (interval: 1 hour)");
    tokio::spawn(deletion_warning_cron(pool.clone()));
    info!("Workspace deletion 48h-warning cron task started (interval: 1 hour)");

    // Schema ownership remains with the Python dashboard during the migration
    // (see HARNESS-ENGINEERING-PLAN.md Section 13). The gateway reads/writes
    // Python's existing tables and therefore runs no migrations of its own.

    let app = create_app(pool, config.jwt_secret).await;

    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    info!("Gateway listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    Ok(())
}

async fn shutdown_signal() {
    use tokio::signal;

    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }

    info!("Shutdown signal received, starting graceful shutdown");
}
