use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde_json::json;
use sqlx::PgPool;

use crate::db;

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/health", get(health_check))
        .route("/health/live", get(liveness))
        .route("/health/ready", get(readiness))
        .with_state(pool)
}

async fn health_check(State(pool): State<PgPool>) -> impl IntoResponse {
    let db_status = match db::health_check(&pool).await {
        Ok(_) => "healthy",
        Err(_) => "unhealthy",
    };
    
    Json(json!({
        "status": if db_status == "healthy" { "healthy" } else { "degraded" },
        "service": "autoniix-gateway",
        "version": env!("CARGO_PKG_VERSION"),
        "checks": {
            "database": db_status
        }
    }))
}

async fn liveness() -> StatusCode {
    StatusCode::OK
}

async fn readiness(State(pool): State<PgPool>) -> impl IntoResponse {
    let db_healthy = db::health_check(&pool).await.is_ok();
    
    if db_healthy {
        (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "checks": {
                    "database": "ok",
                }
            })),
        )
    } else {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "status": "not_ready",
                "checks": {
                    "database": "failed",
                }
            })),
        )
    }
}
