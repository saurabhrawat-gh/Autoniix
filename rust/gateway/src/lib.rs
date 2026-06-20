mod auth;
mod config;
mod db;
mod error;
mod extractors;
mod health;
mod middleware;
mod observability;
mod routes;

pub use auth::{AuthServiceImpl, JwtManager};
pub use config::Config;
pub use db::{create_pool, health_check};
pub use error::{ApiError, ApiResult};
pub use extractors::{AuthUser, RequireAdmin, RequireOwner};
pub use middleware::Principal;

use axum::{middleware as axum_middleware, Router};
use std::sync::Arc;
use tower_http::{compression::CompressionLayer, cors::CorsLayer, trace::TraceLayer};

pub async fn create_app(pool: sqlx::PgPool, jwt_secret: String) -> Router {
    let jwt_manager = Arc::new(JwtManager::new(&jwt_secret));
    let auth_service = AuthServiceImpl::new(pool.clone(), jwt_manager.clone());
    
    let protected_routes = Router::new()
        .merge(routes::user::routes(pool.clone()))
        .layer(axum_middleware::from_fn(middleware::require_auth_middleware));
    
    Router::new()
        .merge(health::routes(pool.clone()))
        .merge(routes::api_routes())
        .merge(routes::auth::routes(auth_service))
        .merge(protected_routes)
        .layer(axum_middleware::from_fn_with_state(
            jwt_manager,
            middleware::auth_middleware,
        ))
        .layer(TraceLayer::new_for_http())
        .layer(CompressionLayer::new())
        .layer(CorsLayer::permissive())
}

#[doc(hidden)]
pub async fn create_test_app() -> Router {
    use sqlx::postgres::PgPoolOptions;
    
    let database_url = std::env::var("TEST_DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://localhost/autoniix_test".to_string());
    
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("Failed to connect to test database");
    
    // Note: Rust gateway reads Python's existing schema (users, workspaces, workspace_members, sessions).
    // Schema migrations are owned by Python until full migration is complete.
    // Tests assume the Python schema is already present in the test database.
    
    create_app(pool, "test-jwt-secret-key".to_string()).await
}
