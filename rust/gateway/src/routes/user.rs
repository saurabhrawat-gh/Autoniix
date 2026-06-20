use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde::Serialize;
use sqlx::PgPool;

use crate::{
    error::ApiResult,
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/me", get(get_current_user))
        .with_state(pool)
}

#[derive(Debug, Serialize)]
struct CurrentUserResponse {
    user: UserInfo,
    workspace: WorkspaceInfo,
}

#[derive(Debug, Serialize)]
struct UserInfo {
    id: i64,
    email: String,
    display_name: Option<String>,
    role: String,
    global_role: String,
}

#[derive(Debug, Serialize)]
struct WorkspaceInfo {
    id: i64,
    name: String,
}

async fn get_current_user(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let (user_id, email, display_name) =
        sqlx::query_as::<_, (i64, String, Option<String>)>(
            "SELECT id, email, display_name FROM users WHERE id = $1",
        )
        .bind(principal.user_id)
        .fetch_one(&pool)
        .await
        .map_err(crate::error::ApiError::Database)?;

    let (workspace_id, workspace_name) = sqlx::query_as::<_, (i64, String)>(
        "SELECT id, name FROM workspaces WHERE id = $1",
    )
    .bind(principal.wid)
    .fetch_one(&pool)
    .await
    .map_err(crate::error::ApiError::Database)?;

    let response = CurrentUserResponse {
        user: UserInfo {
            id: user_id,
            email,
            display_name,
            role: principal.role.clone(),
            global_role: principal.global_role.clone(),
        },
        workspace: WorkspaceInfo {
            id: workspace_id,
            name: workspace_name,
        },
    };
    
    Ok((StatusCode::OK, Json(response)))
}
