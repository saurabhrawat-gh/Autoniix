//! Feature flag CRUD — read for any authenticated user, write for workspace
//! owner/member. Mirrors `src/services/dashboard/v2/flags.py` byte-for-byte:
//! same SQL, same `{data: [...]}` / `{status: "ok"}` envelopes, same
//! `flag.update` audit action, same `before`/`after` payload structure for
//! the audit row.

use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, put},
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
        .route("/api/v2/flags", get(list_flags))
        .route("/api/v2/flags/:key", put(set_flag))
        .with_state(pool)
}

/// One row of `feature_flags`. `payload` is freeform jsonb on the Python
/// side, so we surface it as `serde_json::Value` and let the client deal
/// with the shape.
#[derive(Debug, Serialize, sqlx::FromRow)]
struct FlagRow {
    key: String,
    enabled: bool,
    description: Option<String>,
    payload: Value,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
struct ListFlagsResponse {
    data: Vec<FlagRow>,
}

/// `GET /api/v2/flags` — any authenticated user may read the catalog. No
/// permission gate here matches Python's `Depends(principal_dep)` (i.e. only
/// requires a valid JWT, no role check).
async fn list_flags(
    AuthUser(_principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows: Vec<FlagRow> = sqlx::query_as(
        "SELECT key, enabled, description, payload, updated_at \
           FROM feature_flags \
          ORDER BY key",
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(ListFlagsResponse { data: rows })))
}

/// Request body for `PUT /api/v2/flags/:key`. The Python handler accepts a
/// freeform `body: dict` and pulls `enabled` (default false) + `payload`
/// (default `{}`); we mirror that with explicit defaults so a partial body
/// is still valid.
#[derive(Debug, Deserialize)]
struct SetFlagRequest {
    #[serde(default)]
    enabled: bool,
    #[serde(default = "default_payload")]
    payload: Value,
}

fn default_payload() -> Value {
    json!({})
}

/// Workspace-scoped role gate matching Python's
/// `require_role("owner", "member")` — accepts owner or member, rejects
/// viewer or any other role. Inline (not extracted as middleware) because
/// only one endpoint in this module needs it.
fn require_owner_or_member(principal: &Principal) -> ApiResult<()> {
    match principal.role.as_str() {
        "owner" | "member" => Ok(()),
        _ => Err(ApiError::Forbidden),
    }
}

/// `PUT /api/v2/flags/:key` — toggle and/or replace the payload for a
/// flag. Returns 404 if the key is unknown (we deliberately do NOT auto-
/// create rows; the catalog is curated). Audits both the old and new
/// values so an operator can reconstruct the change history.
async fn set_flag(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(key): Path<String>,
    headers: HeaderMap,
    Json(body): Json<SetFlagRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let before: Option<(bool, Value)> =
        sqlx::query_as("SELECT enabled, payload FROM feature_flags WHERE key = $1")
            .bind(&key)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?;

    let (before_enabled, before_payload) =
        before.ok_or_else(|| ApiError::NotFound("Unknown flag".to_string()))?;

    sqlx::query(
        "UPDATE feature_flags \
            SET enabled = $1, payload = $2::jsonb, updated_at = NOW() \
          WHERE key = $3",
    )
    .bind(body.enabled)
    .bind(&body.payload)
    .bind(&key)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(key.clone()),
            before: Some(json!({
                "enabled": before_enabled,
                "payload": before_payload,
            })),
            after: Some(json!({
                "enabled": body.enabled,
                "payload": body.payload,
            })),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "flag.update", "feature_flag")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}
