use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, patch, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route(
            "/api/v2/lookup-values",
            get(list_lookup_values).post(create_global_value),
        )
        .route(
            "/api/v2/lookup-values/:id",
            patch(update_lookup_value).delete(deactivate_lookup_value),
        )
        .route(
            "/api/v2/workspace/lookup-values",
            post(create_workspace_value),
        )
        .with_state(pool)
}

#[derive(Debug, Deserialize)]
struct ListQuery {
    #[serde(rename = "type")]
    value_type: Option<String>,
    parent_value: Option<String>,
    include_inactive: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct CreateLookupValue {
    #[serde(rename = "type")]
    value_type: String,
    value: String,
    label: String,
    parent_value: Option<String>,
    sort_order: Option<i32>,
}

#[derive(Debug, Deserialize)]
struct UpdateLookupValue {
    label: Option<String>,
    sort_order: Option<i32>,
    is_active: Option<bool>,
}

/// GET /api/v2/lookup-values
/// Returns global values merged with workspace-private values.
/// Global values come first (sort_order), workspace custom values appended.
#[utoipa::path(
    get,
    path = "/api/v2/lookup-values",
    tag = "lookup",
    responses((status = 200, description = "Merged lookup values")),
    security(("cookie_auth" = []))
)]
pub(crate) async fn list_lookup_values(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListQuery>,
) -> ApiResult<impl axum::response::IntoResponse> {
    let include_inactive = q.include_inactive.unwrap_or(false);

    let mut sql = String::from(
        r#"SELECT id, type, value, label, parent_value, workspace_id, sort_order, is_active
             FROM lookup_values
            WHERE (workspace_id IS NULL OR workspace_id = $1)"#,
    );

    if let Some(ref t) = q.value_type {
        sql.push_str(&format!(" AND type = '{}'", t.replace('\'', "''")));
    }
    if let Some(ref pv) = q.parent_value {
        sql.push_str(&format!(" AND parent_value = '{}'", pv.replace('\'', "''")));
    }
    if !include_inactive {
        sql.push_str(" AND is_active = TRUE");
    }
    sql.push_str(" ORDER BY workspace_id NULLS FIRST, sort_order, label");

    let rows = sqlx::query(&sql)
        .bind(principal.wid)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            use sqlx::Row;
            json!({
                "id":           r.get::<i64, _>("id"),
                "type":         r.get::<String, _>("type"),
                "value":        r.get::<String, _>("value"),
                "label":        r.get::<String, _>("label"),
                "parent_value": r.get::<Option<String>, _>("parent_value"),
                "workspace_id": r.get::<Option<i64>, _>("workspace_id"),
                "sort_order":   r.get::<i32, _>("sort_order"),
                "is_active":    r.get::<bool, _>("is_active"),
                "is_custom":    r.get::<Option<i64>, _>("workspace_id").is_some(),
            })
        })
        .collect();

    Ok(Json(json!({ "data": data })))
}

/// POST /api/v2/lookup-values  — superadmin only, creates a global value
#[utoipa::path(
    post,
    path = "/api/v2/lookup-values",
    tag = "lookup",
    responses(
        (status = 201, description = "Global lookup value created"),
        (status = 403, description = "Superadmin only"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn create_global_value(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateLookupValue>,
) -> ApiResult<impl axum::response::IntoResponse> {
    if principal.global_role != "superadmin" {
        return Err(ApiError::Forbidden);
    }

    let row = sqlx::query(
        r#"INSERT INTO lookup_values (type, value, label, parent_value, workspace_id, sort_order)
           VALUES ($1, $2, $3, $4, NULL, $5)
           ON CONFLICT (type, value, workspace_id) DO UPDATE
               SET label = EXCLUDED.label, sort_order = EXCLUDED.sort_order, is_active = TRUE
           RETURNING id, type, value, label, parent_value, workspace_id, sort_order, is_active"#,
    )
    .bind(&body.value_type)
    .bind(&body.value)
    .bind(&body.label)
    .bind(&body.parent_value)
    .bind(body.sort_order.unwrap_or(0))
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "id":           row.get::<i64, _>("id"),
            "type":         row.get::<String, _>("type"),
            "value":        row.get::<String, _>("value"),
            "label":        row.get::<String, _>("label"),
            "parent_value": row.get::<Option<String>, _>("parent_value"),
            "workspace_id": row.get::<Option<i64>, _>("workspace_id"),
            "sort_order":   row.get::<i32, _>("sort_order"),
            "is_active":    row.get::<bool, _>("is_active"),
        })),
    ))
}

/// POST /api/v2/workspace/lookup-values  — workspace owner only, creates workspace-private value
#[utoipa::path(
    post,
    path = "/api/v2/workspace/lookup-values",
    tag = "lookup",
    responses(
        (status = 201, description = "Workspace lookup value created"),
        (status = 403, description = "Owner only"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn create_workspace_value(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateLookupValue>,
) -> ApiResult<impl axum::response::IntoResponse> {
    if principal.role != "owner" {
        return Err(ApiError::Forbidden);
    }

    let row = sqlx::query(
        r#"INSERT INTO lookup_values (type, value, label, parent_value, workspace_id, sort_order)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (type, value, workspace_id) DO UPDATE
               SET label = EXCLUDED.label, sort_order = EXCLUDED.sort_order, is_active = TRUE
           RETURNING id, type, value, label, parent_value, workspace_id, sort_order, is_active"#,
    )
    .bind(&body.value_type)
    .bind(&body.value)
    .bind(&body.label)
    .bind(&body.parent_value)
    .bind(principal.wid)
    .bind(body.sort_order.unwrap_or(0))
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "id":           row.get::<i64, _>("id"),
            "type":         row.get::<String, _>("type"),
            "value":        row.get::<String, _>("value"),
            "label":        row.get::<String, _>("label"),
            "parent_value": row.get::<Option<String>, _>("parent_value"),
            "workspace_id": row.get::<Option<i64>, _>("workspace_id"),
            "sort_order":   row.get::<i32, _>("sort_order"),
            "is_active":    row.get::<bool, _>("is_active"),
        })),
    ))
}

/// PATCH /api/v2/lookup-values/:id
/// Superadmin can update any value; owner can only update their workspace's values.
#[utoipa::path(
    patch,
    path = "/api/v2/lookup-values/{id}",
    tag = "lookup",
    params(("id" = i64, Path, description = "Lookup value id")),
    responses(
        (status = 200, description = "Lookup value updated"),
        (status = 403, description = "Forbidden"),
        (status = 404, description = "Not found"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn update_lookup_value(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(id): Path<i64>,
    Json(body): Json<UpdateLookupValue>,
) -> ApiResult<impl axum::response::IntoResponse> {
    let existing = sqlx::query("SELECT workspace_id FROM lookup_values WHERE id = $1")
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Lookup value not found".to_string()))?;

    use sqlx::Row;
    let row_workspace: Option<i64> = existing.get("workspace_id");

    match row_workspace {
        None => {
            if principal.global_role != "superadmin" {
                return Err(ApiError::Forbidden);
            }
        }
        Some(wid) => {
            if wid != principal.wid || principal.role != "owner" {
                return Err(ApiError::Forbidden);
            }
        }
    }

    sqlx::query(
        r#"UPDATE lookup_values
              SET label      = COALESCE($2, label),
                  sort_order = COALESCE($3, sort_order),
                  is_active  = COALESCE($4, is_active)
            WHERE id = $1"#,
    )
    .bind(id)
    .bind(&body.label)
    .bind(body.sort_order)
    .bind(body.is_active)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok(Json(json!({ "status": "updated", "id": id })))
}

/// DELETE /api/v2/lookup-values/:id  — soft-delete (set is_active = false)
#[utoipa::path(
    delete,
    path = "/api/v2/lookup-values/{id}",
    tag = "lookup",
    params(("id" = i64, Path, description = "Lookup value id")),
    responses(
        (status = 204, description = "Lookup value deactivated"),
        (status = 403, description = "Forbidden"),
        (status = 404, description = "Not found"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn deactivate_lookup_value(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(id): Path<i64>,
) -> ApiResult<impl axum::response::IntoResponse> {
    let existing = sqlx::query("SELECT workspace_id FROM lookup_values WHERE id = $1")
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Lookup value not found".to_string()))?;

    use sqlx::Row;
    let row_workspace: Option<i64> = existing.get("workspace_id");

    match row_workspace {
        None => {
            if principal.global_role != "superadmin" {
                return Err(ApiError::Forbidden);
            }
        }
        Some(wid) => {
            if wid != principal.wid || principal.role != "owner" {
                return Err(ApiError::Forbidden);
            }
        }
    }

    sqlx::query("UPDATE lookup_values SET is_active = FALSE WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    Ok(StatusCode::NO_CONTENT)
}
