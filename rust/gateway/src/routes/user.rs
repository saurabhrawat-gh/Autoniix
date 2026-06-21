use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::get, Json, Router};
use serde::Serialize;
use sqlx::PgPool;

use crate::{
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/me", get(get_current_user))
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
    // The JWT `sub` claim carries the user id as a string; parse it to match the
    // bigint `users.id` column.
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    // `display_name` is the only field sourced from the DB; everything else comes
    // from the verified JWT principal (mirrors Python `v2/auth.py` /me).
    let display_name: Option<String> =
        sqlx::query_scalar::<_, Option<String>>("SELECT display_name FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?
            .flatten();

    // Resolve permissions for the workspace-scoped role from the shared
    // `role_permissions` matrix (same source as Python `_permissions.py`).
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

    // A known role with zero seeded permissions means the RBAC matrix is
    // uninitialized — surface 503 rather than silently hiding every nav item.
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
