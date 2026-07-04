//! Generic reverse-proxy helpers used by thin proxy route modules.
//!
//! Each Python v2 module that hasn't been natively re-implemented in Rust yet
//! gets a route file that uses these helpers to forward traffic transparently
//! to the Python BFF (`PYTHON_BFF_URL`, default `http://localhost:8020`).

use axum::{
    body::Bytes,
    http::{HeaderMap, Method, StatusCode, Uri},
    response::IntoResponse,
    Json,
};
use serde_json::Value;

use crate::error::{ApiError, ApiResult};

fn bff_base() -> String {
    std::env::var("PYTHON_BFF_URL").unwrap_or_else(|_| "http://localhost:8020".to_string())
}

/// Build the full proxy URL by replacing just the origin (scheme+host+port)
/// of the BFF base with the request path+query from the incoming URI.
pub fn proxy_url(uri: &Uri) -> String {
    let base = bff_base();
    let path_and_query = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or(uri.path());
    format!("{base}{path_and_query}")
}

/// Fully transparent reverse proxy: forwards method, body, Content-Type, and
/// the Authorization header (Bearer token) to the BFF, then streams back the
/// status + JSON response.
pub async fn proxy_request(
    method: Method,
    target_url: String,
    auth_header: Option<String>,
    content_type: Option<String>,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let client = reqwest::Client::new();

    let mut builder = match method {
        Method::GET => client.get(&target_url),
        Method::POST => client.post(&target_url),
        Method::PUT => client.put(&target_url),
        Method::PATCH => client.patch(&target_url),
        Method::DELETE => client.delete(&target_url),
        Method::HEAD => client.head(&target_url),
        other => {
            return Err(ApiError::Internal(format!(
                "proxy: unsupported method {other}"
            )))
        }
    };

    if let Some(auth) = auth_header {
        builder = builder.header("Authorization", auth);
    }

    if !body.is_empty() {
        let ct = content_type
            .as_deref()
            .unwrap_or("application/json");
        builder = builder
            .header("content-type", ct)
            .body(body.to_vec());
    }

    let resp = builder
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("proxy: {e}")))?;

    let status =
        StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let body: Value = resp.json().await.unwrap_or(Value::Null);
    Ok((status, Json(body)))
}

/// Extract the `Authorization` header value as a `String` from an axum `HeaderMap`.
pub fn extract_auth(headers: &HeaderMap) -> Option<String> {
    headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}

/// Extract the `Content-Type` header value as a `String`.
pub fn extract_content_type(headers: &HeaderMap) -> Option<String> {
    headers
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}
