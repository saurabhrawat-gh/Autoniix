use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/me", get(get_current_user))
        .route("/api/v2/me/sessions", get(list_sessions))
        .route("/api/v2/me/sessions/:session_id", delete(revoke_session))
        .route("/api/v2/users", get(list_users))
        .route(
            "/api/v2/users/transfer-superadmin/:target_user_id",
            post(transfer_superadmin),
        )
        .route("/api/v2/users/:user_id/disable", put(disable_user))
        .route("/api/v2/users/:user_id/enable", put(enable_user))
        .route("/api/v2/users/:user_id", delete(delete_user))
        .with_state(pool)
}

/// `/me` response — mirrors Python `v2/auth.py` which wraps the payload in a
/// top-level `data` object. The dashboard reads `data.permissions` to gate nav.
#[derive(Debug, Serialize)]
struct CurrentUserResponse {
    data: CurrentUserData,
}

#[derive(Debug, Serialize)]
struct CurrentUserData {
    user_id: i64,
    email: String,
    role: String,
    global_role: String,
    workspace_id: i64,
    source: String,
    display_name: Option<String>,
    initials: String,
    permissions: Vec<String>,
}

async fn get_current_user(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    let display_name: Option<String> =
        sqlx::query_scalar::<_, Option<String>>("SELECT display_name FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?
            .flatten();

    let mut permissions: Vec<String> =
        sqlx::query_scalar::<_, String>("SELECT permission FROM role_permissions WHERE role = $1")
            .bind(&principal.role)
            .fetch_all(&pool)
            .await
            .map_err(|e| {
                ApiError::ServiceUnavailable(format!(
                    "role_permissions matrix unreadable for role={}: {e}",
                    principal.role
                ))
            })?;
    permissions.sort();

    let known_role = matches!(principal.role.as_str(), "owner" | "member" | "viewer");
    if permissions.is_empty() && known_role {
        return Err(ApiError::ServiceUnavailable(format!(
            "role_permissions matrix has no rows for known role={} — \
             RBAC catalog appears uninitialized",
            principal.role
        )));
    }

    let initials = compute_initials(display_name.as_deref(), &principal.email);

    let response = CurrentUserResponse {
        data: CurrentUserData {
            user_id,
            email: principal.email.clone(),
            role: principal.role.clone(),
            global_role: principal.global_role.clone(),
            workspace_id: principal.wid,
            source: "v2_jwt".to_string(),
            display_name,
            initials,
            permissions,
        },
    };

    Ok((StatusCode::OK, Json(response)))
}

/// `GET /api/v2/users` — superadmin-only list of all users, each with their
/// workspace memberships. Mirrors Python `v2/users.py::list_users` byte-for-byte:
/// same SQL (filters out tombstoned `deleted-*@deleted.local` rows), same
/// top-level `{data: [...]}` envelope, same field names.
#[derive(Debug, Serialize)]
struct ListUsersResponse {
    data: Vec<UserRow>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct UserRow {
    id: i64,
    email: String,
    display_name: Option<String>,
    global_role: String,
    mfa_enabled: bool,
    email_verified: bool,
    disabled: bool,
    last_login_at: Option<DateTime<Utc>>,
    created_at: DateTime<Utc>,
    /// Aggregated as JSON by Postgres so we don't have to do a second query
    /// per row. Shape: `[{workspace_id, workspace_name, workspace_role}, ...]`.
    workspaces: Value,
}

async fn list_users(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    if principal.global_role != "superadmin" {
        return Err(ApiError::Forbidden);
    }

    let rows: Vec<UserRow> = sqlx::query_as::<_, UserRow>(
        r#"SELECT u.id, u.email, u.display_name, u.role AS global_role,
                  u.mfa_enabled, u.email_verified, u.disabled,
                  u.last_login_at, u.created_at,
                  COALESCE(
                      JSON_AGG(
                          JSON_BUILD_OBJECT(
                              'workspace_id',   wm.workspace_id,
                              'workspace_name', w.name,
                              'workspace_role', wm.role
                          ) ORDER BY w.name
                      ) FILTER (WHERE wm.workspace_id IS NOT NULL),
                      '[]'::json
                  ) AS workspaces
             FROM users u
             LEFT JOIN workspace_members wm ON wm.user_id = u.id
             LEFT JOIN workspaces w ON w.id = wm.workspace_id
            WHERE u.email NOT LIKE 'deleted-%@deleted.local'
            GROUP BY u.id
            ORDER BY u.id"#,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(ListUsersResponse { data: rows })))
}

/// Superadmin gate used by every `/api/v2/users/*` admin endpoint. Mirrors
/// Python's `require_global_role("superadmin")` dependency. Inline here
/// because there is no general-purpose role middleware yet — the only other
/// caller would be `list_users`, which we leave as-is for now to minimize
/// churn.
fn require_superadmin(principal: &crate::middleware::Principal) -> ApiResult<()> {
    if principal.global_role != "superadmin" {
        return Err(ApiError::Forbidden);
    }
    Ok(())
}

/// Parse JWT `sub` (string) into a bigint `users.id`. Returns Unauthorized
/// (not BadRequest) on parse failure: a malformed `sub` means the token is
/// corrupt, so the safest response is to force re-auth.
fn principal_user_id(principal: &crate::middleware::Principal) -> ApiResult<i64> {
    principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)
}

/// `POST /api/v2/users/transfer-superadmin/:target_user_id` — atomic role
/// swap. Caller becomes 'user', target becomes 'superadmin'. Mirrors Python
/// `v2/users.py::transfer_superadmin` byte-for-byte including the audit
/// `user.superadmin.transfer` action label.
async fn transfer_superadmin(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(target_user_id): Path<i64>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_superadmin(&principal)?;
    let actor_id = principal_user_id(&principal)?;

    if actor_id == target_user_id {
        return Err(ApiError::Validation(
            "You are already the superadmin.".to_string(),
        ));
    }

    // Tuple shape matches Python's `SELECT id, role, disabled`.
    let target: Option<(i64, String, bool)> =
        sqlx::query_as("SELECT id, role, disabled FROM users WHERE id = $1")
            .bind(target_user_id)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?;

    let (_id, target_role, target_disabled) =
        target.ok_or_else(|| ApiError::NotFound("Target user not found".to_string()))?;

    if target_disabled {
        return Err(ApiError::Conflict(
            "Cannot transfer superadmin to a disabled account. Enable the account first."
                .to_string(),
        ));
    }
    if target_role == "superadmin" {
        return Err(ApiError::Conflict(
            "Target is already superadmin.".to_string(),
        ));
    }

    // Both UPDATEs must succeed together: a half-applied swap would leave the
    // platform with two superadmins (or zero). Wrap in a transaction.
    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    sqlx::query("UPDATE users SET role='user' WHERE id = $1")
        .bind(actor_id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    sqlx::query("UPDATE users SET role='superadmin' WHERE id = $1")
        .bind(target_user_id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(target_user_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "user.superadmin.transfer", "user")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// `PUT /api/v2/users/:user_id/disable` — disable a user account and revoke
/// all active sessions. Mirrors Python `v2/users.py::disable_user`.
async fn disable_user(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(user_id): Path<i64>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_superadmin(&principal)?;
    let actor_id = principal_user_id(&principal)?;

    if actor_id == user_id {
        return Err(ApiError::ForbiddenWith(
            "You cannot disable your own account.".to_string(),
        ));
    }

    let target: Option<(String,)> = sqlx::query_as("SELECT role FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    let (target_role,) = target.ok_or_else(|| ApiError::NotFound("User not found".to_string()))?;

    if target_role == "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "Cannot disable the superadmin account. Transfer superadmin ownership first."
                .to_string(),
        ));
    }

    sqlx::query("UPDATE users SET disabled = TRUE WHERE id = $1")
        .bind(user_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;
    // Revoke any currently-active sessions so the user is signed out everywhere.
    sqlx::query(
        "UPDATE sessions SET revoked_at = NOW() \
           WHERE user_id = $1 AND revoked_at IS NULL",
    )
    .bind(user_id)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(user_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "user.disable", "user")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// `PUT /api/v2/users/:user_id/enable` — re-enable a previously-disabled user.
/// Mirrors Python `v2/users.py::enable_user`. Idempotent.
async fn enable_user(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(user_id): Path<i64>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_superadmin(&principal)?;

    sqlx::query("UPDATE users SET disabled = FALSE WHERE id = $1")
        .bind(user_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(user_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "user.enable", "user")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// `DELETE /api/v2/users/:user_id` — soft-delete (tombstone) a user account.
/// Mirrors Python `v2/users.py::delete_user`: revokes sessions, drops
/// workspace memberships, and rewrites the user row with a sentinel email so
/// the unique-email constraint remains satisfied while the row is preserved
/// for audit history.
async fn delete_user(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(user_id): Path<i64>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_superadmin(&principal)?;
    let actor_id = principal_user_id(&principal)?;

    if actor_id == user_id {
        return Err(ApiError::Validation(
            "Cannot delete your own account — use the profile page to delete it".to_string(),
        ));
    }

    let target: Option<(String,)> = sqlx::query_as("SELECT role FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    let (target_role,) = target.ok_or_else(|| ApiError::NotFound("User not found".to_string()))?;

    if target_role == "superadmin" {
        return Err(ApiError::Conflict(
            "Cannot delete the superadmin account. Transfer superadmin ownership first."
                .to_string(),
        ));
    }

    let tombstone_email = format!("deleted-{user_id}@deleted.local");

    // Transaction: all three writes (session revocation, membership cleanup,
    // tombstone) must commit together or none at all. A partial delete would
    // leave dangling workspace_members rows.
    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    sqlx::query(
        "UPDATE sessions SET revoked_at = NOW() \
           WHERE user_id = $1 AND revoked_at IS NULL",
    )
    .bind(user_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query("DELETE FROM workspace_members WHERE user_id = $1")
        .bind(user_id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE users SET \
            email = $1, \
            password_hash = NULL, \
            display_name = 'Deleted User', \
            disabled = TRUE, \
            mfa_enabled = FALSE, \
            mfa_secret = NULL \
          WHERE id = $2",
    )
    .bind(&tombstone_email)
    .bind(user_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(user_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "user.delete", "user")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

/// Response item for a single active session.
#[derive(Debug, Serialize)]
struct SessionItem {
    id: i64,
    ip: Option<String>,
    user_agent: Option<String>,
    created_at: DateTime<Utc>,
    last_seen_at: DateTime<Utc>,
    expires_at: DateTime<Utc>,
}

/// `GET /api/v2/me/sessions` — list all active (non-revoked, non-rotated,
/// non-expired) sessions for the authenticated user.
async fn list_sessions(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    #[allow(clippy::type_complexity)]
    let rows: Vec<(
        i64,
        Option<String>,
        Option<String>,
        DateTime<Utc>,
        DateTime<Utc>,
        DateTime<Utc>,
    )> = sqlx::query_as(
        "SELECT id, ip, user_agent, created_at, last_seen_at, expires_at \
             FROM sessions \
             WHERE user_id = $1 \
               AND revoked_at IS NULL \
               AND rotated_at IS NULL \
               AND expires_at > NOW() \
             ORDER BY last_seen_at DESC",
    )
    .bind(user_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let sessions: Vec<SessionItem> = rows
        .into_iter()
        .map(
            |(id, ip, user_agent, created_at, last_seen_at, expires_at)| SessionItem {
                id,
                ip,
                user_agent,
                created_at,
                last_seen_at,
                expires_at,
            },
        )
        .collect();

    Ok((StatusCode::OK, Json(json!({ "data": sessions }))))
}

/// `DELETE /api/v2/me/sessions/:session_id` — revoke a specific session.
/// Returns 403 if the session does not belong to the authenticated user.
async fn revoke_session(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(session_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    // Verify ownership before mutating.
    let owner_id: Option<i64> = sqlx::query_scalar("SELECT user_id FROM sessions WHERE id = $1")
        .bind(session_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

    match owner_id {
        None => return Err(ApiError::NotFound("Session not found".to_string())),
        Some(oid) if oid != user_id => {
            return Err(ApiError::ForbiddenWith(
                "You can only revoke your own sessions".to_string(),
            ))
        }
        _ => {}
    }

    sqlx::query("UPDATE sessions SET revoked_at = NOW() WHERE id = $1")
        .bind(session_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

/// Derive user initials: first + last initial of `display_name`, else the first
/// character of the email. Mirrors Python `v2/auth.py` /me initials logic.
fn compute_initials(display_name: Option<&str>, email: &str) -> String {
    if let Some(name) = display_name {
        let parts: Vec<&str> = name.split_whitespace().collect();
        if !parts.is_empty() {
            let mut initials = String::new();
            if let Some(c) = parts[0].chars().next() {
                initials.push(c);
            }
            if parts.len() > 1 {
                if let Some(c) = parts[parts.len() - 1].chars().next() {
                    initials.push(c);
                }
            }
            return initials.to_uppercase();
        }
    }
    email
        .chars()
        .next()
        .map(|c| c.to_uppercase().to_string())
        .unwrap_or_default()
}
