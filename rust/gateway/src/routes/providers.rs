//! Thin proxy routes for `/api/v2/providers/**` — forwards all traffic to the
//! Python BFF (`PYTHON_BFF_URL`). Includes sub-paths for change-requests and
//! youtube-oauth registered under the same `/api/v2/providers` prefix.

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
        .route("/api/v2/providers", any(handle))
        .route("/api/v2/providers/*path", any(handle))
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
