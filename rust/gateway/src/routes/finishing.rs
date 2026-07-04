//! Thin proxy routes for finishing-related endpoints — forwards all traffic
//! to the Python BFF (`PYTHON_BFF_URL`).
//!
//! finishing.py has `prefix=""` so its routes land directly under `/api/v2/`:
//!   GET/PUT /channels/{channel_id}/settings/finishing
//!   GET     /finishing/presets

use axum::{
    body::Bytes,
    http::{HeaderMap, Method, Uri},
    response::IntoResponse,
    routing::any,
    Router,
};

use crate::{error::ApiResult, extractors::AuthUser, routes::proxy};

pub fn routes() -> Router {
    Router::new()
        .route(
            "/api/v2/channels/:channel_id/settings/finishing",
            any(handle),
        )
        .route("/api/v2/finishing/presets", any(handle))
}

pub(crate) async fn handle(
    AuthUser(_principal): AuthUser,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let url = proxy::proxy_url(&uri);
    let auth = proxy::extract_auth(&headers);
    let ct = proxy::extract_content_type(&headers);
    proxy::proxy_request(method, url, auth, ct, body).await
}
