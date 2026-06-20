use anyhow::Result;
use sqlx::{postgres::PgPoolOptions, PgPool};
use std::time::Duration;

pub async fn create_pool(database_url: &str) -> Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(20)
        .min_connections(5)
        .acquire_timeout(Duration::from_secs(3))
        .idle_timeout(Duration::from_secs(600))
        .max_lifetime(Duration::from_secs(1800))
        .connect(database_url)
        .await?;
    
    tracing::info!("Database connection pool created");
    
    Ok(pool)
}

pub async fn health_check(pool: &PgPool) -> Result<bool> {
    sqlx::query("SELECT 1")
        .fetch_one(pool)
        .await?;
    Ok(true)
}
