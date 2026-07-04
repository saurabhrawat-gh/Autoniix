//! Experiment endpoints — proxy to Python BFF (which proxies to admin:8009)
//! with audit logging on write operations.
//! (experiments.py — 6 endpoints)
//!
//! The Admin service owns all A/B-test state; Rust does not hold a local
//! schema for experiments.  We keep the proxy approach but add audit_log
//! so writes appear in the audit trail.

use axum::{
    body::Bytes,
    extract::{Path, Query, State},
    http::{HeaderMap, Method, Uri},
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use serde::Deserialize;
use serde_json::json;
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::ApiResult,
    extractors::AuthUser,
    routes::proxy,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/experiments",              get(list_experiments).post(create_experiment))
        .route("/api/v2/experiments/:name/activate", post(activate))
        .route("/api/v2/experiments/:name/pause",    post(pause))
        .route("/api/v2/experiments/:name/complete", post(complete))
        .route("/api/v2/experiments/:name/results",  get(results))
        .with_state(pool)
}

#[derive(Deserialize)]
struct WinnerQ  { #[serde(default)] winner: String }

// ── GET /experiments ──────────────────────────────────────────────────────────

async fn list_experiments(
    AuthUser(_p): AuthUser,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await
}

// ── POST /experiments ─────────────────────────────────────────────────────────

async fn create_experiment(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let resp = proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.create", target_type: "experiment",
        target_id: None, before: None, after: None, headers: Some(&headers),
    }).await;
    Ok(resp)
}

// ── POST /experiments/:name/activate ─────────────────────────────────────────

async fn activate(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    Path(name): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let resp = proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.activate", target_type: "experiment",
        target_id: Some(name), before: None, after: None, headers: Some(&headers),
    }).await;
    Ok(resp)
}

// ── POST /experiments/:name/pause ────────────────────────────────────────────

async fn pause(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    Path(name): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let resp = proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.pause", target_type: "experiment",
        target_id: Some(name), before: None, after: None, headers: Some(&headers),
    }).await;
    Ok(resp)
}

// ── POST /experiments/:name/complete ─────────────────────────────────────────

async fn complete(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    Path(name):  Path<String>,
    Query(q):    Query<WinnerQ>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    let resp = proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.complete", target_type: "experiment",
        target_id: Some(name), before: None,
        after: Some(json!({ "winner": q.winner })), headers: Some(&headers),
    }).await;
    Ok(resp)
}

// ── GET /experiments/:name/results ───────────────────────────────────────────

async fn results(
    AuthUser(_p): AuthUser,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy::proxy_request(method, proxy::proxy_url(&uri), proxy::extract_auth(&headers), proxy::extract_content_type(&headers), body).await
}
