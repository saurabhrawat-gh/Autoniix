// Route submodules. `allow(private_interfaces)` silences the "type more private
// than the item" warnings that appear because request/query structs are still
// module-private while their handlers are now `pub(crate)` (needed by
// `#[utoipa::path]` referencing in `crate::openapi::ApiDoc`). Follow-up story
// A5 will promote the request/response types to `pub(crate)` + `ToSchema`.
#[allow(private_interfaces)]
pub mod auth;
#[allow(private_interfaces)]
pub mod channels;
#[allow(private_interfaces)]
pub mod flags;
#[allow(private_interfaces)]
pub mod lookup_values;
#[allow(private_interfaces)]
pub mod notifications;
#[allow(private_interfaces)]
pub mod system;
#[allow(private_interfaces)]
pub mod user;
#[allow(private_interfaces)]
pub mod voice;
#[allow(private_interfaces)]
pub mod workspace;

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
