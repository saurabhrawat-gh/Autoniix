use anyhow::Result;
use std::net::SocketAddr;
use tracing::info;

use gateway::{create_app, create_pool, Config};

mod observability;

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();

    observability::init_tracing()?;

    let config = Config::from_env()?;
    info!("Starting Autoniix Gateway v{}", env!("CARGO_PKG_VERSION"));
    info!("Environment: {}", config.environment);

    let pool = create_pool(&config.database_url).await?;
    info!("Database connection established");

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
