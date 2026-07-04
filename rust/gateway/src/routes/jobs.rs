//! Native Rust handlers for `/api/v2/jobs/**`
//! (jobs.py — 11 endpoints)
//!
//! Native (DB): output, metadata, approve, reject
//! Proxy+audit:  retry, restart, pause, resume, stop
//! Pure proxy:   active, progress  (require live Temporal status)

use axum::{
    body::Bytes,
    extract::{Path, State},
    http::{HeaderMap, Method, Uri},
    response::IntoResponse,
    routing::{any, get, post},
    Json, Router,
};
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    routes::proxy,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // pure proxy — Temporal live status
        .route("/api/v2/jobs/active",               any(proxy_handle))
        .route("/api/v2/jobs/:id/progress",         any(proxy_handle))
        // native DB reads
        .route("/api/v2/jobs/:id/output",           get(job_output))
        .route("/api/v2/jobs/:id/metadata",         get(job_metadata))
        // native DB writes + audit
        .route("/api/v2/jobs/:id/approve",          post(approve_job))
        .route("/api/v2/jobs/:id/reject",           post(reject_job))
        // proxy + audit
        .route("/api/v2/jobs/:id/retry",            post(retry_job))
        .route("/api/v2/jobs/:id/restart",          post(restart_job))
        .route("/api/v2/jobs/:id/pause",            post(pause_job))
        .route("/api/v2/jobs/:id/resume",           post(resume_job))
        .route("/api/v2/jobs/:id/stop",             post(stop_job))
        .with_state(pool)
}

// ── pure proxy helper ──────────────────────────────────────────────────────────

async fn proxy_handle(
    AuthUser(_p): AuthUser,
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

// ── GET /jobs/:id/output ───────────────────────────────────────────────────────

async fn job_output(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT title, rendered_video_url, thumbnail_variants_urls,
                  youtube_video_id, total_cost::float8 AS "total_cost?: f64", status
             FROM videos WHERE content_id = $1"#,
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Video not found".into()))?;

    let thumbnails: Value = row
        .thumbnail_variants_urls
        .as_deref()
        .and_then(|s| serde_json::from_str(s).ok())
        .unwrap_or_else(|| json!([]));

    let proxy_url = if row.rendered_video_url.is_some() {
        format!("/api/jobs/{content_id}/video")
    } else {
        String::new()
    };

    let yt_id = row.youtube_video_id.clone();
    let yt_url = yt_id
        .as_deref()
        .map(|id| format!("https://youtu.be/{id}"));
    let cost = row.total_cost.unwrap_or(0.0);

    Ok(Json(json!({
        "status": "ok",
        "data": {
            "content_id": content_id,
            "title": row.title,
            "status": row.status,
            "video_url": proxy_url,
            "download_url": proxy_url,
            "thumbnails": thumbnails,
            "youtube_video_id": yt_id,
            "youtube_url": yt_url,
            "total_cost": cost
        }
    })))
}

// ── GET /jobs/:id/metadata ─────────────────────────────────────────────────────

async fn job_metadata(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT title, delivery_result, thumbnail_variants_urls, content_mode
             FROM videos WHERE content_id = $1"#,
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Video not found".into()))?;

    let delivery: Value = row
        .delivery_result
        .as_ref()
        .and_then(|v| serde_json::to_value(v).ok())
        .unwrap_or_else(|| json!({}));

    let thumbnails: Value = row
        .thumbnail_variants_urls
        .as_deref()
        .and_then(|s| serde_json::from_str(s).ok())
        .unwrap_or_else(|| json!([]));

    let title = delivery
        .get("title")
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| row.title.as_deref().unwrap_or(""))
        .to_string();

    Ok(Json(json!({
        "status": "ok",
        "data": {
            "content_id": content_id,
            "title": title,
            "description": delivery.get("description").unwrap_or(&json!("")),
            "tags": delivery.get("tags").unwrap_or(&json!([])),
            "hashtags": delivery.get("hashtags").unwrap_or(&json!([])),
            "category": delivery.get("category").unwrap_or(&json!("")),
            "seo_score": delivery.get("seo_score"),
            "thumbnails": thumbnails,
            "content_mode": row.content_mode
        }
    })))
}

// ── POST /jobs/:id/approve ─────────────────────────────────────────────────────

async fn approve_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM videos WHERE content_id = $1",
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    if exists.is_none() {
        return Err(ApiError::NotFound("Video not found".into()));
    }

    sqlx::query!(
        "UPDATE videos SET approved_at = NOW(), approved_by = $1 WHERE content_id = $2",
        actor.user_id,
        content_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor,
        action: "job.approve",
        target_type: "video",
        target_id: Some(content_id.clone()),
        before: None,
        after: None,
        headers: Some(&headers),
    })
    .await;

    Ok(Json(json!({ "status": "ok", "data": { "content_id": content_id, "approved": true } })))
}

// ── POST /jobs/:id/reject ──────────────────────────────────────────────────────

async fn reject_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM videos WHERE content_id = $1",
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    if exists.is_none() {
        return Err(ApiError::NotFound("Video not found".into()));
    }

    sqlx::query!(
        "UPDATE videos SET status = 'rejected', updated_at = NOW() WHERE content_id = $1",
        content_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor,
        action: "job.reject",
        target_type: "video",
        target_id: Some(content_id.clone()),
        before: None,
        after: None,
        headers: Some(&headers),
    })
    .await;

    Ok(Json(json!({ "status": "ok", "data": { "content_id": content_id, "rejected": true } })))
}

// ── proxy + audit helpers ──────────────────────────────────────────────────────

async fn proxy_and_audit(
    actor: crate::middleware::Principal,
    pool: PgPool,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
    action: &str,
    content_id: String,
) -> ApiResult<impl IntoResponse> {
    let url = proxy::proxy_url(&uri);
    let auth = proxy::extract_auth(&headers);
    let ct = proxy::extract_content_type(&headers);
    let resp = proxy::proxy_request(method, url, auth, ct, body).await?;
    audit_log(&pool, AuditCtx {
        actor: &actor,
        action,
        target_type: "video",
        target_id: Some(content_id),
        before: None,
        after: None,
        headers: Some(&headers),
    })
    .await;
    Ok(resp)
}

async fn retry_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy_and_audit(actor, pool, method, uri, headers, body, "job.retry", content_id).await
}

async fn restart_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy_and_audit(actor, pool, method, uri, headers, body, "job.restart", content_id).await
}

async fn pause_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy_and_audit(actor, pool, method, uri, headers, body, "job.pause", content_id).await
}

async fn resume_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy_and_audit(actor, pool, method, uri, headers, body, "job.resume", content_id).await
}

async fn stop_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<impl IntoResponse> {
    proxy_and_audit(actor, pool, method, uri, headers, body, "job.stop", content_id).await
}
