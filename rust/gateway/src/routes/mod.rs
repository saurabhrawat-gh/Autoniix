pub mod auth;
pub mod channels;
pub mod flags;
pub mod notifications;
pub mod system;
pub mod user;

use axum::{routing::get, Json, Router};
use serde_json::json;

pub fn api_routes() -> Router {
    Router::new().route("/api/v2/info", get(api_info))
}

async fn api_info() -> Json<serde_json::Value> {
    Json(json!({
        "name": "Autoniix Gateway",
        "version": env!("CARGO_PKG_VERSION"),
        "protocol": "REST + Connect-RPC (dual mode)",
        "status": "auth_complete"
    }))
}
