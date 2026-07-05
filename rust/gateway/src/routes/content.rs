//! Native Rust handlers for `/api/v2/content/**`
//! (content.py — 8 endpoints)
//!
//! Dynamic-filter queries (list, search, calendar, stats) use
//! `sqlx::QueryBuilder` so they are not in the `.sqlx` cache.
//! Bulk, detail, trigger-history use static macros.
//! POST /trigger: fully native — inserts content_triggers, calls BFF channel
//! trigger endpoint, updates trigger record with result.

use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::{PgPool, Row};

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::Principal,
};

fn bff_base() -> String {
    std::env::var("PYTHON_BFF_URL").unwrap_or_else(|_| "http://localhost:8020".to_string())
}

fn require_owner_or_member(p: &Principal) -> ApiResult<()> {
    match p.role.as_str() {
        "owner" | "member" => Ok(()),
        _ => Err(ApiError::Forbidden),
    }
}

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // static sub-paths MUST come before /:content_id
        .route("/api/v2/content/search", get(search_content))
        .route("/api/v2/content/calendar", get(calendar))
        .route("/api/v2/content/bulk", post(bulk_action))
        .route("/api/v2/content/triggers/history", get(list_triggers))
        .route("/api/v2/content/stats", get(content_stats))
        .route("/api/v2/content/trigger", post(trigger_content))
        .route("/api/v2/content/:content_id", get(get_content_detail))
        .route("/api/v2/content", get(list_content))
        .with_state(pool)
}

// ── query/body structs ─────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct ListQ {
    channel_id: Option<String>,
    #[serde(default = "d_week")]
    group: String,
    status: Option<String>,
    review_state: Option<String>,
    content_mode: Option<String>,
    cursor: Option<String>,
    #[serde(default = "d_50")]
    limit: i64,
}
fn d_week() -> String {
    "week".into()
}
fn d_50() -> i64 {
    50
}

#[derive(Deserialize)]
struct SearchQ {
    q: String,
    channel_id: Option<String>,
    #[serde(default = "d_40")]
    limit: i64,
}
fn d_40() -> i64 {
    40
}

#[derive(Deserialize)]
struct CalendarQ {
    channel_id: Option<String>,
    start: String,
    end: String,
}

#[derive(Deserialize)]
struct TriggersQ {
    channel_id: Option<String>,
    #[serde(default = "d_20")]
    limit: i64,
}

#[derive(Deserialize)]
struct TriggerIn {
    channel_id: String,
    #[serde(default = "d_long_form")]
    content_mode: String,
    topic_hint: Option<String>,
    #[serde(default)]
    topic_candidates: Vec<String>,
    scheduled_for: Option<String>,
    max_cost_usd: Option<f64>,
}
fn d_long_form() -> String {
    "long_form".into()
}
fn d_20() -> i64 {
    20
}

#[derive(Deserialize)]
struct StatsQ {
    channel_id: Option<String>,
    #[serde(default = "d_week")]
    period: String,
}

#[derive(Deserialize)]
struct BulkActionIn {
    action: String,
    ids: Vec<String>,
    note: Option<String>,
}

// ── GET /content ───────────────────────────────────────────────────────────────

async fn list_content(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListQ>,
) -> ApiResult<Json<Value>> {
    const VALID_GROUPS: &[&str] = &["day", "week", "month", "quarter", "year"];
    if !VALID_GROUPS.contains(&q.group.as_str()) {
        return Err(ApiError::Validation(format!(
            "group must be one of {VALID_GROUPS:?}"
        )));
    }
    let lim = q.limit.clamp(1, 500);
    let trunc = q.group.as_str();

    let mut qb: sqlx::QueryBuilder<sqlx::Postgres> = sqlx::QueryBuilder::new(format!(
        r#"SELECT content_id, channel_id, status, content_mode, title, topic,
                      selected_hook, review_state,
                      authenticity_score::float8    AS authenticity_score,
                      uniqueness_score::float8      AS uniqueness_score,
                      thumbnail_variants_urls, rendered_video_url,
                      youtube_video_id,
                      total_cost::float8            AS total_cost,
                      final_composite_score::float8 AS final_composite_score,
                      current_phase, created_at, scheduled_at, published_at,
                      date_trunc('{}', created_at)::date AS bucket
               FROM videos WHERE 1=1"#,
        trunc
    ));

    if let Some(ref v) = q.channel_id {
        qb.push(" AND channel_id = ").push_bind(v);
    }
    if let Some(ref v) = q.status {
        qb.push(" AND status = ").push_bind(v);
    }
    if let Some(ref v) = q.review_state {
        qb.push(" AND review_state = ").push_bind(v);
    }
    if let Some(ref v) = q.content_mode {
        qb.push(" AND content_mode = ").push_bind(v);
    }
    if let Some(ref cur) = q.cursor {
        let dt = chrono::DateTime::parse_from_rfc3339(cur)
            .map(|d| d.with_timezone(&chrono::Utc))
            .map_err(|_| ApiError::Validation("cursor must be ISO datetime".into()))?;
        qb.push(" AND created_at < ").push_bind(dt);
    }
    qb.push(" ORDER BY created_at DESC LIMIT ")
        .push_bind(lim + 1);

    let rows = qb
        .build()
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let has_more = rows.len() as i64 > lim;
    let rows = &rows[..rows.len().min(lim as usize)];

    let mut group_order: Vec<String> = Vec::new();
    let mut group_map: std::collections::HashMap<String, Vec<Value>> =
        std::collections::HashMap::new();
    for r in rows {
        let bucket: chrono::NaiveDate = r.try_get("bucket").unwrap_or_default();
        let key = bucket.to_string();
        let item = json!({
            "content_id": r.try_get::<Option<String>, _>("content_id").ok().flatten(),
            "channel_id": r.try_get::<Option<String>, _>("channel_id").ok().flatten(),
            "status": r.try_get::<Option<String>, _>("status").ok().flatten(),
            "content_mode": r.try_get::<Option<String>, _>("content_mode").ok().flatten(),
            "title": r.try_get::<Option<String>, _>("title").ok().flatten(),
            "topic": r.try_get::<Option<String>, _>("topic").ok().flatten(),
            "selected_hook": r.try_get::<Option<String>, _>("selected_hook").ok().flatten(),
            "review_state": r.try_get::<Option<String>, _>("review_state").ok().flatten(),
            "authenticity_score": r.try_get::<Option<f64>, _>("authenticity_score").ok().flatten(),
            "uniqueness_score": r.try_get::<Option<f64>, _>("uniqueness_score").ok().flatten(),
            "thumbnail_variants_urls": r.try_get::<Option<String>, _>("thumbnail_variants_urls").ok().flatten(),
            "rendered_video_url": r.try_get::<Option<String>, _>("rendered_video_url").ok().flatten(),
            "youtube_video_id": r.try_get::<Option<String>, _>("youtube_video_id").ok().flatten(),
            "total_cost": r.try_get::<Option<f64>, _>("total_cost").ok().flatten(),
            "final_composite_score": r.try_get::<Option<f64>, _>("final_composite_score").ok().flatten(),
            "current_phase": r.try_get::<Option<String>, _>("current_phase").ok().flatten(),
            "created_at": r.try_get::<Option<chrono::DateTime<chrono::Utc>>, _>("created_at").ok().flatten(),
            "scheduled_at": r.try_get::<Option<chrono::DateTime<chrono::Utc>>, _>("scheduled_at").ok().flatten(),
            "published_at": r.try_get::<Option<chrono::DateTime<chrono::Utc>>, _>("published_at").ok().flatten(),
        });
        if !group_map.contains_key(&key) {
            group_order.push(key.clone());
        }
        group_map.entry(key).or_default().push(item);
    }

    let next_cursor = if has_more {
        rows.last()
            .and_then(|r| {
                r.try_get::<Option<chrono::DateTime<chrono::Utc>>, _>("created_at")
                    .ok()
                    .flatten()
            })
            .map(|d| d.to_rfc3339())
    } else {
        None
    };

    Ok(Json(json!({
        "data": {
            "groups": group_order.iter().map(|k| json!({"label": k, "items": &group_map[k]})).collect::<Vec<_>>(),
            "group_kind": q.group,
            "next_cursor": next_cursor,
            "count": rows.len()
        }
    })))
}

// ── GET /content/search ────────────────────────────────────────────────────────

async fn search_content(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<SearchQ>,
) -> ApiResult<Json<Value>> {
    if q.q.len() < 2 {
        return Err(ApiError::Validation(
            "q must be at least 2 characters".into(),
        ));
    }
    let lim = q.limit.clamp(1, 200);

    let rows = if let Some(ref ch) = q.channel_id {
        sqlx::query!(
            r#"SELECT content_id, channel_id, title, topic, selected_hook, status,
                      review_state, created_at,
                      ts_rank(title_tsv, plainto_tsquery('english', $1)) AS rank
                 FROM videos
                WHERE title_tsv @@ plainto_tsquery('english', $1) AND channel_id = $2
                ORDER BY rank DESC, created_at DESC
                LIMIT $3"#,
            q.q,
            ch,
            lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| {
            json!({
                "content_id": r.content_id, "channel_id": r.channel_id,
                "title": r.title, "topic": r.topic, "selected_hook": r.selected_hook,
                "status": r.status, "review_state": r.review_state,
                "created_at": r.created_at, "rank": r.rank
            })
        })
        .collect::<Vec<_>>()
    } else {
        sqlx::query!(
            r#"SELECT content_id, channel_id, title, topic, selected_hook, status,
                      review_state, created_at,
                      ts_rank(title_tsv, plainto_tsquery('english', $1)) AS rank
                 FROM videos
                WHERE title_tsv @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC, created_at DESC
                LIMIT $2"#,
            q.q,
            lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| {
            json!({
                "content_id": r.content_id, "channel_id": r.channel_id,
                "title": r.title, "topic": r.topic, "selected_hook": r.selected_hook,
                "status": r.status, "review_state": r.review_state,
                "created_at": r.created_at, "rank": r.rank
            })
        })
        .collect::<Vec<_>>()
    };
    Ok(Json(json!({ "data": rows })))
}

// ── GET /content/calendar ──────────────────────────────────────────────────────

async fn calendar(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<CalendarQ>,
) -> ApiResult<Json<Value>> {
    let mut qb: sqlx::QueryBuilder<sqlx::Postgres> = sqlx::QueryBuilder::new(
        r#"SELECT content_id, channel_id, content_mode, status, review_state,
                  title, topic, authenticity_score::float8 AS authenticity_score,
                  COALESCE(published_at, scheduled_at, created_at)::date AS day,
                  published_at, scheduled_at, created_at
             FROM videos
            WHERE COALESCE(published_at, scheduled_at, created_at) >= "#,
    );
    qb.push_bind(q.start.clone())
        .push("::date AND COALESCE(published_at, scheduled_at, created_at) < ")
        .push_bind(q.end.clone())
        .push("::date");
    if let Some(ref ch) = q.channel_id {
        qb.push(" AND channel_id = ").push_bind(ch);
    }
    qb.push(" ORDER BY day ASC, created_at ASC");

    let rows = qb
        .build()
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let mut day_order: Vec<String> = Vec::new();
    let mut day_map: std::collections::HashMap<String, Vec<Value>> =
        std::collections::HashMap::new();
    for r in &rows {
        let day: chrono::NaiveDate = r.try_get("day").unwrap_or_default();
        let key = day.to_string();
        let entry = json!({
            "content_id":  r.try_get::<Option<String>,_>("content_id").ok().flatten(),
            "channel_id":  r.try_get::<Option<String>,_>("channel_id").ok().flatten(),
            "content_mode":r.try_get::<Option<String>,_>("content_mode").ok().flatten(),
            "status":      r.try_get::<Option<String>,_>("status").ok().flatten(),
            "review_state":r.try_get::<Option<String>,_>("review_state").ok().flatten(),
            "title":       r.try_get::<Option<String>,_>("title").ok().flatten().or_else(|| r.try_get::<Option<String>,_>("topic").ok().flatten()),
            "authenticity_score": r.try_get::<Option<f64>,_>("authenticity_score").ok().flatten(),
            "published_at":  r.try_get::<Option<chrono::DateTime<chrono::Utc>>,_>("published_at").ok().flatten(),
            "scheduled_at":  r.try_get::<Option<chrono::DateTime<chrono::Utc>>,_>("scheduled_at").ok().flatten(),
        });
        if !day_map.contains_key(&key) {
            day_order.push(key.clone());
        }
        day_map.entry(key).or_default().push(entry);
    }
    // Rebuild as ordered object for JSON output
    let data: serde_json::Map<String, Value> = day_order
        .iter()
        .map(|k| (k.clone(), Value::Array(day_map[k].clone())))
        .collect();
    Ok(Json(
        json!({ "data": data, "start": q.start, "end": q.end }),
    ))
}

// ── POST /content/bulk ────────────────────────────────────────────────────────

async fn bulk_action(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<BulkActionIn>,
) -> ApiResult<Json<Value>> {
    if body.ids.is_empty() {
        return Ok(Json(json!({ "status": "noop" })));
    }
    let ids = body.ids.as_slice();
    let affected: u64 = match body.action.as_str() {
        "archive" => sqlx::query!(
            "UPDATE videos SET status='archived', updated_at=NOW()
              WHERE content_id = ANY($1) AND status NOT IN ('archived','published')",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        "approve" => sqlx::query!(
            "UPDATE videos SET review_state='approved', updated_at=NOW() WHERE content_id = ANY($1)",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        "reject" => sqlx::query!(
            "UPDATE videos SET review_state='rejected', updated_at=NOW() WHERE content_id = ANY($1)",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        "retry" => sqlx::query!(
            "UPDATE videos SET status='pending', error_message=NULL, updated_at=NOW()
              WHERE content_id = ANY($1) AND status IN ('failed','stopped')",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        "regenerate" => sqlx::query!(
            "UPDATE videos SET review_state='regenerating', status='pending', updated_at=NOW() WHERE content_id = ANY($1)",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        "delete" => sqlx::query!(
            "UPDATE videos SET status='archived', updated_at=NOW() WHERE content_id = ANY($1)",
            ids,
        ).execute(&pool).await.map_err(ApiError::Database)?.rows_affected(),
        other => return Err(ApiError::Validation(format!("Unknown action {other:?}"))),
    };
    audit_log(
        &pool,
        AuditCtx {
            actor: &actor,
            action: Box::leak(format!("content.bulk.{}", body.action).into_boxed_str()),
            target_type: "video",
            target_id: Some(format!("{} items", body.ids.len())),
            before: None,
            after: Some(json!({ "ids": body.ids, "affected": affected, "note": body.note })),
            headers: Some(&headers),
        },
    )
    .await;
    Ok(Json(json!({ "status": "ok", "affected": affected })))
}

// ── GET /content/triggers/history ─────────────────────────────────────────────

async fn list_triggers(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<TriggersQ>,
) -> ApiResult<Json<Value>> {
    let lim = q.limit.clamp(1, 100);
    let rows = if let Some(ref ch) = q.channel_id {
        sqlx::query!(
            r#"SELECT id, channel_id, content_mode, topic_hint, scheduled_for,
                      triggered_by, status, content_id, error, created_at, updated_at
                 FROM content_triggers WHERE channel_id = $1
                 ORDER BY created_at DESC LIMIT $2"#,
            ch,
            lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "channel_id": r.channel_id, "content_mode": r.content_mode,
                "topic_hint": r.topic_hint, "scheduled_for": r.scheduled_for,
                "triggered_by": r.triggered_by, "status": r.status,
                "content_id": r.content_id, "error": r.error,
                "created_at": r.created_at, "updated_at": r.updated_at
            })
        })
        .collect::<Vec<_>>()
    } else {
        sqlx::query!(
            r#"SELECT id, channel_id, content_mode, topic_hint, scheduled_for,
                      triggered_by, status, content_id, error, created_at, updated_at
                 FROM content_triggers ORDER BY created_at DESC LIMIT $1"#,
            lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "channel_id": r.channel_id, "content_mode": r.content_mode,
                "topic_hint": r.topic_hint, "scheduled_for": r.scheduled_for,
                "triggered_by": r.triggered_by, "status": r.status,
                "content_id": r.content_id, "error": r.error,
                "created_at": r.created_at, "updated_at": r.updated_at
            })
        })
        .collect::<Vec<_>>()
    };
    Ok(Json(json!({ "data": rows })))
}

// ── GET /content/stats ────────────────────────────────────────────────────────

async fn content_stats(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<StatsQ>,
) -> ApiResult<Json<Value>> {
    let trunc = match q.period.as_str() {
        "day" => "day",
        "month" => "month",
        _ => "week",
    };
    let lookback_days: i64 = match q.period.as_str() {
        "day" => 30,
        "month" => 365,
        _ => 84,
    };
    let cutoff = chrono::Utc::now() - chrono::Duration::days(lookback_days);

    let mut qb: sqlx::QueryBuilder<sqlx::Postgres> = sqlx::QueryBuilder::new(format!(
        r#"SELECT status, content_mode, COUNT(*) AS cnt,
                  AVG(total_cost)::float8           AS avg_cost,
                  AVG(final_composite_score)::float8 AS avg_score,
                  date_trunc('{}', created_at)::date AS bucket
             FROM videos WHERE created_at >= "#,
        trunc,
    ));
    qb.push_bind(cutoff);
    if let Some(ref ch) = q.channel_id {
        qb.push(" AND channel_id = ").push_bind(ch);
    }
    qb.push(" GROUP BY status, content_mode, bucket ORDER BY bucket DESC");

    let bucket_rows = qb
        .build()
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let mut qb2: sqlx::QueryBuilder<sqlx::Postgres> = sqlx::QueryBuilder::new(
        r#"SELECT channel_id,
                  COUNT(*) FILTER (WHERE status IN ('completed','published','delivered')) AS done,
                  COUNT(*) FILTER (WHERE status = 'running')  AS running,
                  COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
                  SUM(total_cost)::float8 AS total_cost
             FROM videos WHERE 1=1"#,
    );
    if let Some(ref ch) = q.channel_id {
        qb2.push(" AND channel_id = ").push_bind(ch);
    }
    qb2.push(" GROUP BY channel_id");
    let chan_rows = qb2
        .build()
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let buckets = bucket_rows
        .iter()
        .map(|r| {
            json!({
                "status":       r.try_get::<Option<String>,_>("status").ok().flatten(),
                "content_mode": r.try_get::<Option<String>,_>("content_mode").ok().flatten(),
                "cnt":          r.try_get::<Option<i64>,_>("cnt").ok().flatten(),
                "avg_cost":     r.try_get::<Option<f64>,_>("avg_cost").ok().flatten(),
                "avg_score":    r.try_get::<Option<f64>,_>("avg_score").ok().flatten(),
                "bucket":       r.try_get::<Option<chrono::NaiveDate>,_>("bucket").ok().flatten(),
            })
        })
        .collect::<Vec<_>>();

    let by_channel = chan_rows
        .iter()
        .map(|r| {
            json!({
                "channel_id": r.try_get::<Option<String>,_>("channel_id").ok().flatten(),
                "done":       r.try_get::<Option<i64>,_>("done").ok().flatten(),
                "running":    r.try_get::<Option<i64>,_>("running").ok().flatten(),
                "failed":     r.try_get::<Option<i64>,_>("failed").ok().flatten(),
                "total_cost": r.try_get::<Option<f64>,_>("total_cost").ok().flatten(),
            })
        })
        .collect::<Vec<_>>();

    Ok(Json(
        json!({ "data": { "buckets": buckets, "by_channel": by_channel } }),
    ))
}

// ── GET /content/:content_id ──────────────────────────────────────────────────

async fn get_content_detail(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(content_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT content_id, channel_id, status, content_mode, title, topic,
                  selected_hook, review_state,
                  authenticity_score::float8  AS "authenticity_score?: f64",
                  uniqueness_score::float8    AS "uniqueness_score?: f64",
                  thumbnail_variants_urls, rendered_video_url, youtube_video_id,
                  total_cost::float8          AS "total_cost?: f64",
                  final_composite_score::float8 AS "final_composite_score?: f64",
                  error_message, checkpoint, created_at, scheduled_at,
                  published_at, updated_at, environment
             FROM videos WHERE content_id = $1"#,
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Content not found".into()))?;

    let events = sqlx::query!(
        "SELECT phase, status, duration_ms, detail, created_at
           FROM job_events WHERE content_id = $1 ORDER BY created_at ASC",
        content_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let review = sqlx::query!(
        r#"SELECT rs.id, rs.state, rs.opened_at,
                  COUNT(DISTINCT fc.id) AS comment_count,
                  COUNT(DISTINCT ra.id) AS approval_count
             FROM review_sessions rs
             LEFT JOIN frame_comments fc  ON fc.session_id = rs.id
             LEFT JOIN review_approvals ra ON ra.session_id = rs.id
            WHERE rs.video_id = $1
            GROUP BY rs.id ORDER BY rs.opened_at DESC LIMIT 1"#,
        content_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok(Json(json!({
        "data": {
            "content_id": row.content_id, "channel_id": row.channel_id,
            "status": row.status, "content_mode": row.content_mode,
            "title": row.title, "topic": row.topic,
            "selected_hook": row.selected_hook, "review_state": row.review_state,
            "authenticity_score": row.authenticity_score,
            "uniqueness_score": row.uniqueness_score,
            "thumbnail_variants_urls": row.thumbnail_variants_urls,
            "rendered_video_url": row.rendered_video_url,
            "youtube_video_id": row.youtube_video_id,
            "total_cost": row.total_cost,
            "final_composite_score": row.final_composite_score,
            "error_message": row.error_message, "checkpoint": row.checkpoint,
            "created_at": row.created_at, "scheduled_at": row.scheduled_at,
            "published_at": row.published_at, "updated_at": row.updated_at,
            "environment": row.environment,
            "events": events.iter().map(|e| json!({
                "phase": e.phase, "status": e.status,
                "duration_ms": e.duration_ms, "detail": e.detail,
                "created_at": e.created_at
            })).collect::<Vec<_>>(),
            "review_session": review.map(|r| json!({
                "id": r.id, "state": r.state, "opened_at": r.opened_at,
                "comment_count": r.comment_count, "approval_count": r.approval_count
            }))
        }
    })))
}

// ── POST /content/trigger ─────────────────────────────────────────────────────

async fn trigger_content(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<TriggerIn>,
) -> ApiResult<Json<Value>> {
    require_owner_or_member(&actor)?;

    let triggered_by: Option<i64> = actor.user_id.parse().ok();
    let scheduled_for: Option<chrono::DateTime<chrono::Utc>> =
        body.scheduled_for.as_deref().and_then(|s| s.parse().ok());

    let trigger_id = sqlx::query_scalar!(
        r#"INSERT INTO content_triggers
               (channel_id, content_mode, topic_hint, scheduled_for, triggered_by, status)
           VALUES ($1, $2, $3, $4, $5, 'queued')
           RETURNING id"#,
        body.channel_id,
        body.content_mode,
        body.topic_hint,
        scheduled_for,
        triggered_by,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    // ── call BFF channel-trigger (starts Temporal VideoProductionWorkflow) ──
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);

    let mut payload = json!({ "content_mode": body.content_mode });
    if let Some(h) = &body.topic_hint {
        payload["topic_candidates"] = json!([h]);
    }
    if !body.topic_candidates.is_empty() {
        payload["topic_candidates"] = json!(body.topic_candidates);
    }
    if let Some(c) = body.max_cost_usd {
        payload["max_cost_usd"] = json!(c);
    }

    let bff_url = format!("{}/api/channels/{}/trigger", bff_base(), body.channel_id);
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .build()
        .map_err(|e| ApiError::Internal(format!("reqwest init: {e}")))?;
    let mut req = client.post(&bff_url).json(&payload);
    if let Some(a) = &auth {
        req = req.header("Authorization", a);
    }

    let (triggered, content_id) = match req.send().await {
        Ok(resp) if resp.status().as_u16() < 400 => {
            let data: Value = resp.json().await.unwrap_or(Value::Null);
            let cid = data
                .get("data")
                .and_then(|d| d.get("content_id"))
                .and_then(|v| v.as_str())
                .or_else(|| data.get("content_id").and_then(|v| v.as_str()))
                .map(String::from);
            (true, cid)
        }
        _ => (false, None),
    };

    sqlx::query!(
        "UPDATE content_triggers SET status = $2, content_id = $3, updated_at = NOW() WHERE id = $1",
        trigger_id,
        if triggered { "running" } else { "failed" },
        content_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "content.trigger", target_type: "channel",
        target_id: Some(body.channel_id.clone()), before: None,
        after: Some(json!({ "trigger_id": trigger_id, "triggered": triggered, "content_id": content_id })),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({
        "status": if triggered { "ok" } else { "queued" },
        "trigger_id": trigger_id,
        "content_id": content_id,
    })))
}
