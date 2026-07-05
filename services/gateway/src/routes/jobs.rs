//! Native Rust handlers for `/api/v2/jobs/**`
//! (jobs.py — 11 endpoints)
//!
//! Native (DB): output, metadata, approve, reject, active, progress
//! Proxy+audit:  retry, restart, pause, resume, stop  (Temporal signals)

use axum::{
    body::Bytes,
    extract::{Path, Query, State},
    http::{HeaderMap, Method, Uri},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
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
        // native DB reads — active pipeline + per-job progress
        .route("/api/v2/jobs/active", get(job_active))
        .route("/api/v2/jobs/:id/progress", get(job_progress))
        // native DB reads
        .route("/api/v2/jobs/:id/output", get(job_output))
        .route("/api/v2/jobs/:id/metadata", get(job_metadata))
        // native DB writes + audit
        .route("/api/v2/jobs/:id/approve", post(approve_job))
        .route("/api/v2/jobs/:id/reject", post(reject_job))
        // proxy + audit
        .route("/api/v2/jobs/:id/retry", post(retry_job))
        .route("/api/v2/jobs/:id/restart", post(restart_job))
        .route("/api/v2/jobs/:id/pause", post(pause_job))
        .route("/api/v2/jobs/:id/resume", post(resume_job))
        .route("/api/v2/jobs/:id/stop", post(stop_job))
        .with_state(pool)
}

// ── GET /jobs/active ──────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct ActiveQ {
    #[serde(default)]
    channel_id: Option<String>,
    #[serde(default = "default_limit")]
    limit: i64,
}
fn default_limit() -> i64 {
    50
}

async fn job_active(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ActiveQ>,
) -> ApiResult<Json<Value>> {
    let lim = q.limit.clamp(1, 100);
    let rows =
        if let Some(ref ch) = q.channel_id {
            sqlx::query!(
            r#"SELECT content_id, channel_id, title, status, content_mode, created_at, updated_at
               FROM videos
               WHERE status IN ('queued','running','processing','pending')
                 AND channel_id = $1
               ORDER BY created_at DESC LIMIT $2"#,
            ch, lim,
        ).fetch_all(&pool).await.map_err(ApiError::Database)?
         .into_iter().map(|r| json!({
            "content_id": r.content_id, "channel_id": r.channel_id,
            "title": r.title, "status": r.status,
            "content_mode": r.content_mode,
            "created_at": r.created_at, "updated_at": r.updated_at,
         })).collect::<Vec<Value>>()
        } else {
            sqlx::query!(
            r#"SELECT content_id, channel_id, title, status, content_mode, created_at, updated_at
               FROM videos
               WHERE status IN ('queued','running','processing','pending')
               ORDER BY created_at DESC LIMIT $1"#,
            lim,
        ).fetch_all(&pool).await.map_err(ApiError::Database)?
         .into_iter().map(|r| json!({
            "content_id": r.content_id, "channel_id": r.channel_id,
            "title": r.title, "status": r.status,
            "content_mode": r.content_mode,
            "created_at": r.created_at, "updated_at": r.updated_at,
         })).collect::<Vec<Value>>()
        };

    Ok(Json(
        json!({ "status": "ok", "data": rows, "count": rows.len() }),
    ))
}

// ── GET /jobs/:id/progress ────────────────────────────────────────────────────

async fn job_progress(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT content_id, channel_id, title, status, content_mode,
                  rendered_video_url,
                  total_cost::float8 AS "total_cost?: f64",
                  created_at, updated_at
           FROM videos WHERE content_id = $1"#,
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Job not found".into()))?;

    Ok(Json(json!({
        "status": "ok",
        "data": {
            "content_id":   row.content_id,
            "channel_id":   row.channel_id,
            "title":        row.title,
            "status":       row.status,
            "content_mode": row.content_mode,
            "has_output":   row.rendered_video_url.is_some(),
            "total_cost":   row.total_cost.unwrap_or(0.0),
            "created_at":   row.created_at,
            "updated_at":   row.updated_at,
        }
    })))
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
    let yt_url = yt_id.as_deref().map(|id| format!("https://youtu.be/{id}"));
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
    let exists = sqlx::query_scalar!("SELECT 1 FROM videos WHERE content_id = $1", content_id,)
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

    audit_log(
        &pool,
        AuditCtx {
            actor: &actor,
            action: "job.approve",
            target_type: "video",
            target_id: Some(content_id.clone()),
            before: None,
            after: None,
            headers: Some(&headers),
        },
    )
    .await;

    Ok(Json(
        json!({ "status": "ok", "data": { "content_id": content_id, "approved": true } }),
    ))
}

// ── POST /jobs/:id/reject ──────────────────────────────────────────────────────

async fn reject_job(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let exists = sqlx::query_scalar!("SELECT 1 FROM videos WHERE content_id = $1", content_id,)
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

    audit_log(
        &pool,
        AuditCtx {
            actor: &actor,
            action: "job.reject",
            target_type: "video",
            target_id: Some(content_id.clone()),
            before: None,
            after: None,
            headers: Some(&headers),
        },
    )
    .await;

    Ok(Json(
        json!({ "status": "ok", "data": { "content_id": content_id, "rejected": true } }),
    ))
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
    audit_log(
        &pool,
        AuditCtx {
            actor: &actor,
            action,
            target_type: "video",
            target_id: Some(content_id),
            before: None,
            after: None,
            headers: Some(&headers),
        },
    )
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
    proxy_and_audit(
        actor,
        pool,
        method,
        uri,
        headers,
        body,
        "job.retry",
        content_id,
    )
    .await
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
    proxy_and_audit(
        actor,
        pool,
        method,
        uri,
        headers,
        body,
        "job.restart",
        content_id,
    )
    .await
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
    proxy_and_audit(
        actor,
        pool,
        method,
        uri,
        headers,
        body,
        "job.pause",
        content_id,
    )
    .await
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
    proxy_and_audit(
        actor,
        pool,
        method,
        uri,
        headers,
        body,
        "job.resume",
        content_id,
    )
    .await
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
    proxy_and_audit(
        actor, pool, method, uri, headers, body, "job.stop", content_id,
    )
    .await
}
