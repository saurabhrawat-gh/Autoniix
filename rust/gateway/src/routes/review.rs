//! Thin proxy routes for `/api/v2/review/**` and `/api/v2/channels/*/settings/review`
//! — forwards all traffic to the Python BFF (`PYTHON_BFF_URL`).
//!
//! Covers: review.py and review_config.py Python modules.
//! review_config has `prefix=""` so its routes appear under `/channels/`.

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
        // review module (prefix "/review")
        .route("/api/v2/review", any(handle))
        .route("/api/v2/review/*path", any(handle))
        // review_config: GET/PUT /channels/{channel_id}/settings/review
        .route(
            "/api/v2/channels/:channel_id/settings/review",
            any(handle),
        )
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
