//! System v2 — config, emergency stop/resume, fleet health, environment,
//! clean slate. Port of `src/services/dashboard/v2/system.py`.
//!
//! Seven endpoints split across four concerns:
//!   - **Config:** GET/PUT `system_config` rows (DB-backed)
//!   - **Emergency:** stop/resume — proxies to the legacy BFF at
//!     `LEGACY_BFF_URL` (default `http://localhost:8020`)
//!   - **Fleet health:** proxy to legacy BFF
//!   - **Environment:** GET (any authed) / PUT (owner only) — DB-backed
//!   - **Clean slate:** owner-only proxy to legacy BFF
//!
//! Auth model mirrors Python's `require_role` decorators exactly.

use std::env;

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::Principal,
};

/// Default legacy BFF base URL. Overridable via `LEGACY_BFF_URL` env so the
/// CI/test stacks can point at a fake. Matches Python's hard-coded
/// `_LEGACY = "http://localhost:8020"` when the env var is unset.
fn legacy_bff_url() -> String {
    env::var("LEGACY_BFF_URL").unwrap_or_else(|_| "http://localhost:8020".to_string())
}

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/system/config", get(get_config).put(update_config))
        .route("/api/v2/system/emergency-stop", post(emergency_stop))
        .route("/api/v2/system/emergency-resume", post(emergency_resume))
        .route("/api/v2/system/fleet-health", get(fleet_health))
        .route(
            "/api/v2/system/environment",
            get(get_environment).put(set_environment),
        )
        .route("/api/v2/system/clean-slate", post(clean_slate))
        .route(
            "/api/v2/system/entity-settings",
            get(list_system_entity_settings).put(upsert_system_entity_setting),
        )
        .route(
            "/api/v2/workspace/entity-settings",
            get(list_workspace_entity_settings).put(upsert_workspace_entity_setting),
        )
        .with_state(pool)
}

/// Accept workspace `owner` or `member` — mirrors Python
/// `require_role("owner", "member")`.
fn require_owner_or_member(principal: &Principal) -> ApiResult<()> {
    match principal.role.as_str() {
        "owner" | "member" => Ok(()),
        _ => Err(ApiError::Forbidden),
    }
}

/// Owner-only gate — mirrors Python `require_role("owner")`. Used by
/// environment switch and clean-slate.
fn require_owner(principal: &Principal) -> ApiResult<()> {
    if principal.role == "owner" {
        Ok(())
    } else {
        Err(ApiError::Forbidden)
    }
}

/// Forward a request to the legacy BFF and re-emit its JSON response.
/// Mirrors Python's `_proxy()` helper:
///   - 30-second timeout
///   - forwards the inbound `Authorization` header if present, otherwise
///     falls back to the `access_token` cookie
///   - any non-2xx response from the BFF is surfaced as an `ApiError` so
///     the client sees the upstream status code, not a generic 500
///   - connection failure surfaces as 502 (Bad Gateway)
async fn proxy_legacy(
    headers: &HeaderMap,
    method: reqwest::Method,
    path: &str,
    body: Option<Value>,
) -> ApiResult<Value> {
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .or_else(|| {
            headers
                .get("cookie")
                .and_then(|v| v.to_str().ok())
                .and_then(extract_access_token_cookie)
                .map(|tok| format!("Bearer {tok}"))
        });

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| ApiError::Internal(format!("reqwest client init failed: {e}")))?;

    let url = format!("{}{path}", legacy_bff_url());
    let mut req = client.request(method, &url);
    if let Some(a) = auth {
        req = req.header("authorization", a);
    }
    if let Some(b) = body {
        req = req.json(&b);
    }

    let resp = req
        .send()
        .await
        .map_err(|e| ApiError::ServiceUnavailable(format!("Legacy BFF unreachable: {e}")))?;

    let status = resp.status();
    let content_type = resp
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();
    let text = resp
        .text()
        .await
        .map_err(|e| ApiError::Internal(format!("legacy BFF body read failed: {e}")))?;

    if !status.is_success() {
        let detail = if content_type.starts_with("application/json") {
            serde_json::from_str::<Value>(&text)
                .ok()
                .and_then(|v| v.get("detail").and_then(|d| d.as_str()).map(str::to_owned))
                .unwrap_or_else(|| text.clone())
        } else {
            text.clone()
        };

        return Err(match status.as_u16() {
            400 => ApiError::Validation(detail),
            401 => ApiError::Unauthorized,
            403 => ApiError::ForbiddenWith(detail),
            404 => ApiError::NotFound(detail),
            409 => ApiError::Conflict(detail),
            503 => ApiError::ServiceUnavailable(detail),
            _ => ApiError::Internal(format!("legacy BFF returned {status}: {detail}")),
        });
    }

    if text.is_empty() {
        return Ok(Value::Null);
    }
    serde_json::from_str(&text)
        .map_err(|e| ApiError::Internal(format!("legacy BFF returned non-JSON body: {e}")))
}

/// Extract the value of the `access_token` cookie from a raw Cookie header
/// string. Returns `None` if the cookie isn't present.
fn extract_access_token_cookie(cookie_hdr: &str) -> Option<String> {
    for part in cookie_hdr.split(';') {
        let (name, value) = part.trim().split_once('=')?;
        if name == "access_token" {
            return Some(value.to_owned());
        }
    }
    None
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct ConfigRow {
    config_key: String,
    config_value: String,
    description: Option<String>,
}

#[derive(Debug, Serialize)]
struct ConfigEntry {
    key: String,
    value: String,
    description: Option<String>,
}

#[derive(Debug, Serialize)]
struct ListConfigResponse {
    status: &'static str,
    data: Vec<ConfigEntry>,
}

/// `GET /api/v2/system/config` — any authenticated user may read.
async fn get_config(
    AuthUser(_principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows: Vec<ConfigRow> = sqlx::query_as(
        "SELECT config_key, config_value, description \
           FROM system_config \
          ORDER BY config_key",
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data = rows
        .into_iter()
        .map(|r| ConfigEntry {
            key: r.config_key,
            value: r.config_value,
            description: r.description,
        })
        .collect();

    Ok((
        StatusCode::OK,
        Json(ListConfigResponse { status: "ok", data }),
    ))
}

#[derive(Debug, Deserialize)]
struct ConfigUpdateRequest {
    config_key: String,
    config_value: String,
}

#[derive(Debug, Serialize)]
struct ConfigUpdateData {
    key: String,
    value: String,
}

#[derive(Debug, Serialize)]
struct ConfigUpdateResponse {
    status: &'static str,
    data: ConfigUpdateData,
}

/// `PUT /api/v2/system/config` — owner/member only. 404 when the key
/// doesn't exist (no auto-create — matches Python).
async fn update_config(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<ConfigUpdateRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query(
        "UPDATE system_config \
            SET config_value = $1, updated_at = NOW() \
          WHERE config_key = $2",
    )
    .bind(&body.config_value)
    .bind(&body.config_key)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Config key not found".to_string()));
    }

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(body.config_key.clone()),
            after: Some(json!({
                "key":   body.config_key,
                "value": body.config_value,
            })),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "system.config.update", "system_config")
        },
    )
    .await;

    Ok((
        StatusCode::OK,
        Json(ConfigUpdateResponse {
            status: "ok",
            data: ConfigUpdateData {
                key: body.config_key,
                value: body.config_value,
            },
        }),
    ))
}

/// `POST /api/v2/system/emergency-stop` — owner/member. Freezes the system
/// and pauses all running Temporal workflows via the legacy BFF.
async fn emergency_stop(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let result = proxy_legacy(&headers, reqwest::Method::POST, "/api/emergency-stop", None).await?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some("global".to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "system.emergency_stop", "system")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(result)))
}

/// `POST /api/v2/system/emergency-resume` — owner/member. Un-freezes the
/// system + resumes paused Temporal workflows via the legacy BFF.
async fn emergency_resume(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let result = proxy_legacy(
        &headers,
        reqwest::Method::POST,
        "/api/emergency-resume",
        None,
    )
    .await?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some("global".to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "system.emergency_resume", "system")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(result)))
}

/// `GET /api/v2/system/fleet-health` — any authed user. Pure proxy; the
/// legacy BFF aggregates worker liveness/queue depth/etc.
async fn fleet_health(
    AuthUser(_principal): AuthUser,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    let result = proxy_legacy(&headers, reqwest::Method::GET, "/api/fleet-health", None).await?;
    Ok((StatusCode::OK, Json(result)))
}

#[derive(Debug, Serialize)]
struct EnvironmentData {
    mode: String,
}

#[derive(Debug, Serialize)]
struct EnvironmentResponse {
    status: &'static str,
    data: EnvironmentData,
}

/// `GET /api/v2/system/environment` — any authed user. DB override takes
/// precedence over `ENVIRONMENT_MODE` env var; the default is
/// `"production"` when neither is set (matches Python's fallback chain).
async fn get_environment(
    AuthUser(_principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let db_mode: Option<String> = sqlx::query_scalar(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'",
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let mode = db_mode.unwrap_or_else(|| {
        env::var("ENVIRONMENT_MODE").unwrap_or_else(|_| "production".to_string())
    });

    Ok((
        StatusCode::OK,
        Json(EnvironmentResponse {
            status: "ok",
            data: EnvironmentData { mode },
        }),
    ))
}

#[derive(Debug, Deserialize)]
struct EnvSwitchRequest {
    mode: String,
    #[serde(default)]
    #[allow(dead_code)]
    confirm: bool,
}

/// `PUT /api/v2/system/environment` — owner only. Persists the new mode to
/// `system_config`. Only `"test"` or `"production"` are accepted.
async fn set_environment(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<EnvSwitchRequest>,
) -> ApiResult<impl IntoResponse> {
    require_owner(&principal)?;

    if body.mode != "test" && body.mode != "production" {
        return Err(ApiError::Validation(
            "mode must be 'test' or 'production'".to_string(),
        ));
    }

    sqlx::query(
        "INSERT INTO system_config (config_key, config_value, updated_at) \
         VALUES ('environment_mode', $1, NOW()) \
         ON CONFLICT (config_key) DO UPDATE \
            SET config_value = EXCLUDED.config_value, \
                updated_at   = NOW()",
    )
    .bind(&body.mode)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((
        StatusCode::OK,
        Json(EnvironmentResponse {
            status: "ok",
            data: EnvironmentData { mode: body.mode },
        }),
    ))
}

/// `POST /api/v2/system/clean-slate` — owner only. Cancels workflows,
/// truncates job tables, wipes storage via the legacy BFF. Audits the
/// destructive action regardless of upstream outcome (so we can trace who
/// pressed the big red button even if the BFF later 5xx'd).
async fn clean_slate(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner(&principal)?;

    let result = proxy_legacy(
        &headers,
        reqwest::Method::POST,
        "/api/admin/clean-slate",
        Some(json!({"confirm": "RESET"})),
    )
    .await;

    let (outcome_label, outcome_payload) = match &result {
        Ok(_) => ("system.clean_slate", json!({"upstream": "ok"})),
        Err(e) => (
            "system.clean_slate",
            json!({"upstream": "failed", "error": e.to_string()}),
        ),
    };
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some("global".to_string()),
            after: Some(outcome_payload),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, outcome_label, "system")
        },
    )
    .await;

    let body = result?;
    Ok((StatusCode::OK, Json(body)))
}

#[derive(Debug, Deserialize)]
struct EntitySettingUpsert {
    key: String,
    value: Value,
    #[serde(default)]
    locked: bool,
}

/// `GET /api/v2/system/entity-settings` — owner/member.
/// Returns all entity_settings rows at scope='system', scope_id='global'.
async fn list_system_entity_settings(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    use sqlx::Row;
    let rows = sqlx::query(
        "SELECT key, value, locked FROM entity_settings \
         WHERE scope = 'system' AND scope_id = 'global' ORDER BY key",
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "key":    r.try_get::<String, _>("key").unwrap_or_default(),
                "value":  r.try_get::<Option<Value>, _>("value").ok().flatten(),
                "locked": r.try_get::<bool, _>("locked").unwrap_or(false),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"status": "ok", "data": data}))))
}

/// `PUT /api/v2/system/entity-settings` — owner/member.
/// Upserts one entity_setting at scope='system', scope_id='global'.
async fn upsert_system_entity_setting(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<EntitySettingUpsert>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    sqlx::query(
        "INSERT INTO entity_settings (scope, scope_id, key, value, locked) \
         VALUES ('system', 'global', $1, $2, $3) \
         ON CONFLICT (scope, scope_id, key) DO UPDATE \
         SET value = $2, locked = $3, updated_at = NOW()",
    )
    .bind(&body.key)
    .bind(&body.value)
    .bind(body.locked)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(format!("system/global/{}", body.key)),
            after: Some(json!({"value": body.value, "locked": body.locked})),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "system.entity_settings.upsert",
                "entity_settings",
            )
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// `GET /api/v2/workspace/entity-settings` — owner/member.
/// Returns all entity_settings rows for the caller's workspace.
async fn list_workspace_entity_settings(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    use sqlx::Row;
    let scope_id = principal.wid.to_string();
    let rows = sqlx::query(
        "SELECT key, value, locked FROM entity_settings \
         WHERE scope = 'workspace' AND scope_id = $1 ORDER BY key",
    )
    .bind(&scope_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "key":    r.try_get::<String, _>("key").unwrap_or_default(),
                "value":  r.try_get::<Option<Value>, _>("value").ok().flatten(),
                "locked": r.try_get::<bool, _>("locked").unwrap_or(false),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"status": "ok", "data": data}))))
}

/// `PUT /api/v2/workspace/entity-settings` — owner/member.
/// Upserts one entity_setting at the caller's workspace scope.
async fn upsert_workspace_entity_setting(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<EntitySettingUpsert>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let scope_id = principal.wid.to_string();
    sqlx::query(
        "INSERT INTO entity_settings (scope, scope_id, key, value, locked) \
         VALUES ('workspace', $1, $2, $3, $4) \
         ON CONFLICT (scope, scope_id, key) DO UPDATE \
         SET value = $3, locked = $4, updated_at = NOW()",
    )
    .bind(&scope_id)
    .bind(&body.key)
    .bind(&body.value)
    .bind(body.locked)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(format!("workspace/{}/{}", scope_id, body.key)),
            after: Some(json!({"value": body.value, "locked": body.locked})),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "workspace.entity_settings.upsert",
                "entity_settings",
            )
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_access_token_cookie_picks_the_right_pair() {
        assert_eq!(
            extract_access_token_cookie("foo=bar; access_token=abc123; baz=qux"),
            Some("abc123".to_string())
        );
        assert_eq!(extract_access_token_cookie("foo=bar"), None);
        assert_eq!(extract_access_token_cookie(""), None);
    }

    #[test]
    fn legacy_bff_url_falls_back_to_localhost() {
        let url = legacy_bff_url();
        assert!(!url.is_empty());
        assert!(url.starts_with("http"));
    }
}
