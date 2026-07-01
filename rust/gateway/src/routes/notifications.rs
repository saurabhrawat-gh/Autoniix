//! Notification center — port of `src/services/dashboard/v2/notifications.py`.
//!
//! Eight endpoints split across two resources:
//!   - **Notifications:** list, create (with 60s dedupe), mark-read
//!   - **Routes:** list, create, update, delete, plus delivery audit log
//!
//! Auth model (mirrors Python):
//!   - List + mark-read: any authenticated user
//!   - Everything else: workspace `owner` or `member`
//!
//! Known divergence (tracked in divergence_registry): Python's
//! `create_notification` calls `dispatch_routes(...)` to fan a notification
//! out to webhooks/email best-effort. The Rust port creates the row and
//! returns; route fan-out lives in a separate background job. The 60-second
//! dedupe window is preserved exactly.

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::Principal,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route(
            "/api/v2/notifications",
            get(list_notifications).post(create_notification),
        )
        .route(
            "/api/v2/notifications/:notification_id/read",
            post(mark_read),
        )
        .route(
            "/api/v2/notifications/routes",
            get(list_routes).post(create_route),
        )
        .route("/api/v2/notifications/routes/:route_id", put(update_route))
        .route(
            "/api/v2/notifications/routes/:route_id",
            delete(delete_route),
        )
        .route("/api/v2/notifications/deliveries", get(list_deliveries))
        .with_state(pool)
}

/// Workspace-scoped owner/member gate, used by every write endpoint and the
/// read endpoints that surface platform operator data (routes, deliveries).
/// Mirrors Python's `require_role("owner", "member")`.
fn require_owner_or_member(principal: &Principal) -> ApiResult<()> {
    match principal.role.as_str() {
        "owner" | "member" => Ok(()),
        _ => Err(ApiError::Forbidden),
    }
}

/// Parse JWT `sub` into a bigint `users.id`. Malformed `sub` => Unauthorized
/// (force re-auth) since it indicates a corrupt token.
fn principal_user_id(principal: &Principal) -> ApiResult<i64> {
    principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct NotificationRow {
    id: i64,
    event_type: String,
    severity: String,
    title: String,
    body: Option<String>,
    payload: Value,
    channel_id: Option<String>,
    video_id: Option<String>,
    dedupe_key: Option<String>,
    created_at: DateTime<Utc>,
    /// `read_by` is `bigint[]` in Postgres; sqlx maps it to `Vec<i64>`. The
    /// array stays small (one entry per user who has dismissed the row).
    read_by: Vec<i64>,
}

#[derive(Debug, Serialize)]
struct ListNotificationsResponse {
    data: Vec<NotificationRow>,
}

#[derive(Debug, Deserialize, Default)]
struct ListNotificationsQuery {
    #[serde(default)]
    unread_only: bool,
    severity: Option<String>,
    #[serde(default = "default_limit")]
    limit: i64,
}

fn default_limit() -> i64 {
    100
}

/// `GET /api/v2/notifications` — paged list of recent notifications. Any
/// authenticated user. Filters compose with Python's exact precedence:
/// optional `severity` first, then optional `unread_only` (requires a
/// non-null user_id, always true in Rust since the JWT enforces a sub), then
/// the limit. We build the WHERE clause dynamically to match the same
/// `$1, $2, …` binding pattern Python uses.
async fn list_notifications(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListNotificationsQuery>,
) -> ApiResult<impl IntoResponse> {
    let mut clauses: Vec<String> = vec!["1=1".to_string()];
    let mut next_idx = 1;

    let severity_arg = q.severity.clone();
    if severity_arg.is_some() {
        clauses.push(format!("severity = ${next_idx}"));
        next_idx += 1;
    }

    let user_id_arg = if q.unread_only {
        let uid = principal_user_id(&principal)?;
        clauses.push(format!("NOT (${next_idx} = ANY(read_by))"));
        next_idx += 1;
        Some(uid)
    } else {
        None
    };

    let limit_idx = next_idx;
    let sql = format!(
        "SELECT id, event_type, severity, title, body, payload, channel_id, \
                 video_id, dedupe_key, created_at, read_by \
            FROM notifications \
           WHERE {} \
           ORDER BY created_at DESC \
           LIMIT ${limit_idx}",
        clauses.join(" AND "),
    );

    let mut query = sqlx::query_as::<_, NotificationRow>(&sql);
    if let Some(sev) = severity_arg {
        query = query.bind(sev);
    }
    if let Some(uid) = user_id_arg {
        query = query.bind(uid);
    }
    query = query.bind(q.limit);

    let rows = query.fetch_all(&pool).await.map_err(ApiError::Database)?;
    Ok((
        StatusCode::OK,
        Json(ListNotificationsResponse { data: rows }),
    ))
}

#[derive(Debug, Deserialize)]
struct CreateNotificationRequest {
    event_type: String,
    #[serde(default = "default_severity")]
    severity: String,
    title: String,
    #[serde(default)]
    body: Option<String>,
    #[serde(default = "default_payload")]
    payload: Value,
    #[serde(default)]
    channel_id: Option<String>,
    #[serde(default)]
    video_id: Option<String>,
    #[serde(default)]
    dedupe_key: Option<String>,
}

fn default_severity() -> String {
    "info".to_string()
}

fn default_payload() -> Value {
    json!({})
}

#[derive(Debug, Serialize)]
struct CreateNotificationResponse {
    status: &'static str,
    id: i64,
    /// Present only when a same-`dedupe_key` row was found inside the
    /// 60-second dedupe window. The Python contract emits the field
    /// conditionally; we use `skip_serializing_if` to match exactly.
    #[serde(skip_serializing_if = "Option::is_none")]
    deduped: Option<bool>,
}

/// `POST /api/v2/notifications` — owner/member only. Honours the 60s
/// `dedupe_key` window: if a row with the same key exists within the last
/// minute, return its id with `deduped: true` instead of inserting a new
/// row. Note: route fan-out (Python's `dispatch_routes`) is intentionally
/// not wired in this port; see module docstring.
async fn create_notification(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateNotificationRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    if let Some(ref key) = body.dedupe_key {
        let existing: Option<i64> = sqlx::query_scalar(
            "SELECT id FROM notifications \
              WHERE dedupe_key = $1 \
                AND created_at > NOW() - INTERVAL '60 seconds'",
        )
        .bind(key)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

        if let Some(id) = existing {
            return Ok((
                StatusCode::OK,
                Json(CreateNotificationResponse {
                    status: "ok",
                    id,
                    deduped: Some(true),
                }),
            ));
        }
    }

    let new_id: i64 = sqlx::query_scalar(
        "INSERT INTO notifications \
            (event_type, severity, title, body, payload, channel_id, \
             video_id, dedupe_key) \
         VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8) \
         RETURNING id",
    )
    .bind(&body.event_type)
    .bind(&body.severity)
    .bind(&body.title)
    .bind(body.body.as_deref())
    .bind(&body.payload)
    .bind(body.channel_id.as_deref())
    .bind(body.video_id.as_deref())
    .bind(body.dedupe_key.as_deref())
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((
        StatusCode::OK,
        Json(CreateNotificationResponse {
            status: "ok",
            id: new_id,
            deduped: None,
        }),
    ))
}

/// `POST /api/v2/notifications/:notification_id/read` — append the current
/// user's id to `read_by`. Idempotent: the `NOT (… = ANY(read_by))` guard
/// prevents the same user from appearing twice. Returns `{"status": "noop"}`
/// if the JWT somehow lacks a parseable user id (matches Python's
/// `if p.user_id is None` branch).
async fn mark_read(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(notification_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let user_id = match principal.user_id.parse::<i64>() {
        Ok(uid) => uid,
        Err(_) => return Ok((StatusCode::OK, Json(json!({"status": "noop"})))),
    };

    sqlx::query(
        "UPDATE notifications \
            SET read_by = array_append(read_by, $1) \
          WHERE id = $2 AND NOT ($1 = ANY(read_by))",
    )
    .bind(user_id)
    .bind(notification_id)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct NotificationRouteRow {
    id: i64,
    name: String,
    event_pattern: String,
    severity_min: String,
    /// `text[]` column → `Vec<String>`. List of channel slugs (e.g. `slack`,
    /// `email`) — the dispatcher uses these to look up channel configs.
    channels: Vec<String>,
    filter: Value,
    config: Value,
    enabled: bool,
}

#[derive(Debug, Serialize)]
struct ListRoutesResponse {
    data: Vec<NotificationRouteRow>,
}

/// `GET /api/v2/notifications/routes` — owner/member only.
async fn list_routes(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let rows: Vec<NotificationRouteRow> = sqlx::query_as(
        "SELECT id, name, event_pattern, severity_min, channels, filter, config, enabled \
           FROM notification_routes \
          ORDER BY id",
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(ListRoutesResponse { data: rows })))
}

#[derive(Debug, Deserialize, Serialize)]
struct RouteRequest {
    name: String,
    event_pattern: String,
    #[serde(default = "default_severity")]
    severity_min: String,
    channels: Vec<String>,
    #[serde(default = "default_payload")]
    filter: Value,
    #[serde(default = "default_payload")]
    config: Value,
    #[serde(default = "default_true")]
    enabled: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Serialize)]
struct CreateRouteResponse {
    status: &'static str,
    id: i64,
}

/// `POST /api/v2/notifications/routes` — create a fan-out route. Audits
/// `notification.route.create` with the full request body as the `after`
/// payload, matching Python's `body.model_dump()`.
async fn create_route(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<RouteRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let new_id: i64 = sqlx::query_scalar(
        "INSERT INTO notification_routes \
            (name, event_pattern, severity_min, channels, filter, config, enabled) \
         VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7) \
         RETURNING id",
    )
    .bind(&body.name)
    .bind(&body.event_pattern)
    .bind(&body.severity_min)
    .bind(&body.channels)
    .bind(&body.filter)
    .bind(&body.config)
    .bind(body.enabled)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let after = serde_json::to_value(&body).unwrap_or(Value::Null);

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(new_id.to_string()),
            after: Some(after),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "notification.route.create",
                "notification_route",
            )
        },
    )
    .await;

    Ok((
        StatusCode::OK,
        Json(CreateRouteResponse {
            status: "ok",
            id: new_id,
        }),
    ))
}

/// `PUT /api/v2/notifications/routes/:route_id` — replace an existing
/// route. Returns 404 if no row matched the id (Python checks the row count
/// via `res.endswith("0")`; we use the cleaner `rows_affected`).
async fn update_route(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(route_id): Path<i64>,
    Json(body): Json<RouteRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query(
        "UPDATE notification_routes \
            SET name = $1, event_pattern = $2, severity_min = $3, channels = $4, \
                filter = $5::jsonb, config = $6::jsonb, enabled = $7 \
          WHERE id = $8",
    )
    .bind(&body.name)
    .bind(&body.event_pattern)
    .bind(&body.severity_min)
    .bind(&body.channels)
    .bind(&body.filter)
    .bind(&body.config)
    .bind(body.enabled)
    .bind(route_id)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Route not found".to_string()));
    }

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// `DELETE /api/v2/notifications/routes/:route_id` — drop a route. Always
/// returns 200/ok per Python's behaviour (no 404 on missing rows).
async fn delete_route(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(route_id): Path<i64>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    sqlx::query("DELETE FROM notification_routes WHERE id = $1")
        .bind(route_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(route_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "notification.route.delete",
                "notification_route",
            )
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct DeliveryRow {
    id: i64,
    notification_id: i64,
    route_id: i64,
    channel: String,
    status: String,
    attempts: i32,
    response: Option<Value>,
    error: Option<String>,
    sent_at: Option<DateTime<Utc>>,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
struct ListDeliveriesResponse {
    data: Vec<DeliveryRow>,
}

#[derive(Debug, Deserialize, Default)]
struct ListDeliveriesQuery {
    notification_id: Option<i64>,
    #[serde(default = "default_limit")]
    limit: i64,
}

/// `GET /api/v2/notifications/deliveries` — owner/member only. Optional
/// `notification_id` filter narrows to one notification's delivery attempts;
/// otherwise returns the global recent-delivery log.
async fn list_deliveries(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListDeliveriesQuery>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let rows: Vec<DeliveryRow> = if let Some(nid) = q.notification_id {
        sqlx::query_as(
            "SELECT id, notification_id, route_id, channel, status, attempts, \
                     response, error, sent_at, created_at \
                FROM notification_deliveries \
               WHERE notification_id = $1 \
               ORDER BY created_at DESC \
               LIMIT $2",
        )
        .bind(nid)
        .bind(q.limit)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
    } else {
        sqlx::query_as(
            "SELECT id, notification_id, route_id, channel, status, attempts, \
                     response, error, sent_at, created_at \
                FROM notification_deliveries \
               ORDER BY created_at DESC \
               LIMIT $1",
        )
        .bind(q.limit)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
    };

    Ok((StatusCode::OK, Json(ListDeliveriesResponse { data: rows })))
}
