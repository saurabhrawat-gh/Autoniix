use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post},
    Json, Router,
};
use chrono::{DateTime, Utc};
use serde::Deserialize;
use serde_json::json;
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/workspaces/:id", delete(delete_workspace))
        .route(
            "/api/v2/workspaces/:id/cancel-deletion",
            post(cancel_deletion),
        )
        .route(
            "/api/v2/workspaces/:id/deletion-status",
            get(deletion_status),
        )
        .with_state(pool)
}

#[derive(Deserialize, Default)]
struct DeleteWorkspaceParams {
    force: Option<bool>,
}

/// `DELETE /api/v2/workspaces/:id`
///
/// Initiates workspace soft-delete with a configurable grace period
/// (`WORKSPACE_DELETION_GRACE_DAYS`, default 7).
///
/// In a single transaction:
/// - Sets `workspaces.deleted_at`, `delete_scheduled_at`, `status = 'pending_deletion'`
/// - Suspends all pending invitations (restorable; `suspended_at` not `cancelled_at`)
/// - Revokes all active sessions for every workspace member
///
/// **Orphan guard (IM-183):** If the requesting user is the owner AND this is
/// their only workspace, the delete is blocked with HTTP 400
/// `last_workspace_deletion` unless a superadmin passes `?force=true`.
/// When force-deleted by a superadmin the user is flagged
/// `needs_workspace_setup = true` so the onboarding wizard is shown on next
/// login.
async fn delete_workspace(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(workspace_id): Path<i64>,
    Query(params): Query<DeleteWorkspaceParams>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    let row: Option<(Option<DateTime<Utc>>, String, i64)> =
        sqlx::query_as("SELECT deleted_at, status, owner_user_id FROM workspaces WHERE id = $1")
            .bind(workspace_id)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?;

    let (deleted_at, _status, owner_user_id) = match row {
        None => return Err(ApiError::NotFound("Workspace not found".to_string())),
        Some(r) => r,
    };

    if deleted_at.is_some() {
        return Err(ApiError::Conflict(
            "Workspace is already pending deletion".to_string(),
        ));
    }

    let is_superadmin = principal.role == "superadmin";
    if !is_superadmin && owner_user_id != user_id {
        return Err(ApiError::ForbiddenWith(
            "Only the workspace owner or a superadmin can delete this workspace".to_string(),
        ));
    }

    let remaining: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) \
         FROM workspace_members wm \
         JOIN workspaces w ON w.id = wm.workspace_id \
         WHERE wm.user_id = $1 \
           AND wm.workspace_id != $2 \
           AND w.deleted_at IS NULL",
    )
    .bind(user_id)
    .bind(workspace_id)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let last_workspace = remaining == 0;
    let force = params.force.unwrap_or(false);

    // IM-183: Block owner from deleting their only workspace unless a
    // superadmin is overriding with ?force=true.
    if last_workspace && !is_superadmin {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error":   "last_workspace_deletion",
                "message": "This is your only workspace. Transfer ownership or delete your account before deleting this workspace."
            })),
        ));
    }
    if last_workspace && is_superadmin && !force {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error":   "last_workspace_deletion",
                "message": "This is the owner's only workspace. Pass ?force=true to override and flag the user for re-onboarding."
            })),
        ));
    }

    let grace_days: i64 = std::env::var("WORKSPACE_DELETION_GRACE_DAYS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(7);

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE workspaces \
         SET deleted_at           = NOW(), \
             delete_scheduled_at  = NOW() + ($1::text || ' days')::INTERVAL, \
             status               = 'pending_deletion' \
         WHERE id = $2",
    )
    .bind(grace_days)
    .bind(workspace_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE workspace_invitations \
         SET suspended_at = NOW() \
         WHERE workspace_id = $1 \
           AND suspended_at IS NULL \
           AND cancelled_at IS NULL \
           AND expires_at > NOW()",
    )
    .bind(workspace_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE sessions SET revoked_at = NOW() \
         WHERE user_id IN ( \
             SELECT user_id FROM workspace_members WHERE workspace_id = $1 \
         ) \
         AND revoked_at IS NULL \
         AND rotated_at IS NULL \
         AND expires_at > NOW()",
    )
    .bind(workspace_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    // IM-183: When superadmin force-deletes the owner's last workspace, flag
    // the owner for re-onboarding so the wizard is shown on next login.
    if last_workspace && is_superadmin && force {
        sqlx::query(
            "UPDATE users SET needs_workspace_setup = TRUE \
             WHERE id = (SELECT owner_user_id FROM workspaces WHERE id = $1)",
        )
        .bind(workspace_id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    }

    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(workspace_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "workspace.soft_delete", "workspace")
        },
    )
    .await;

    Ok((
        StatusCode::OK,
        Json(json!({
            "status":         "pending_deletion",
            "last_workspace": last_workspace,
            "grace_days":     grace_days,
        })),
    ))
}

/// `POST /api/v2/workspaces/:id/cancel-deletion`
///
/// Cancels a pending soft-delete within the grace window.
/// Restores the workspace to `active` and un-suspends all invitations
/// that were suspended (not hard-cancelled) during the deletion initiation.
async fn cancel_deletion(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(workspace_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    #[allow(clippy::type_complexity)]
    let row: Option<(Option<DateTime<Utc>>, Option<DateTime<Utc>>, String, i64)> = sqlx::query_as(
        "SELECT deleted_at, delete_scheduled_at, status, owner_user_id \
             FROM workspaces WHERE id = $1",
    )
    .bind(workspace_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let (deleted_at, delete_scheduled_at, status, owner_user_id) = match row {
        None => return Err(ApiError::NotFound("Workspace not found".to_string())),
        Some(r) => r,
    };

    if deleted_at.is_none() || status != "pending_deletion" {
        return Err(ApiError::Validation(
            "Workspace is not pending deletion".to_string(),
        ));
    }

    if let Some(scheduled) = delete_scheduled_at {
        if scheduled <= Utc::now() {
            return Err(ApiError::Gone(
                "Grace period has expired; workspace cannot be restored".to_string(),
            ));
        }
    }

    let is_superadmin = principal.role == "superadmin";
    if !is_superadmin && owner_user_id != user_id {
        return Err(ApiError::ForbiddenWith(
            "Only the workspace owner or a superadmin can cancel deletion".to_string(),
        ));
    }

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE workspaces \
         SET deleted_at = NULL, delete_scheduled_at = NULL, status = 'active' \
         WHERE id = $1",
    )
    .bind(workspace_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query(
        "UPDATE workspace_invitations \
         SET suspended_at = NULL \
         WHERE workspace_id = $1 \
           AND suspended_at IS NOT NULL \
           AND cancelled_at IS NULL",
    )
    .bind(workspace_id)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(workspace_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "workspace.cancel_deletion", "workspace")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({ "status": "active" }))))
}

/// `GET /api/v2/workspaces/:id/deletion-status`
///
/// Returns the current deletion state of a workspace.
/// Accessible by any workspace member or superadmin.
async fn deletion_status(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(workspace_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    let is_superadmin = principal.role == "superadmin";
    if !is_superadmin {
        let member: Option<(String,)> = sqlx::query_as(
            "SELECT role FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        )
        .bind(workspace_id)
        .bind(user_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

        if member.is_none() {
            return Err(ApiError::ForbiddenWith(
                "You are not a member of this workspace".to_string(),
            ));
        }
    }

    #[allow(clippy::type_complexity)]
    let row: Option<(Option<DateTime<Utc>>, Option<DateTime<Utc>>, String)> = sqlx::query_as(
        "SELECT deleted_at, delete_scheduled_at, status \
             FROM workspaces WHERE id = $1",
    )
    .bind(workspace_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let (deleted_at, scheduled_at, status) = match row {
        None => return Err(ApiError::NotFound("Workspace not found".to_string())),
        Some(r) => r,
    };

    Ok((
        StatusCode::OK,
        Json(json!({
            "status":       status,
            "deleted_at":   deleted_at,
            "scheduled_at": scheduled_at,
            "cancelled":    deleted_at.is_none(),
        })),
    ))
}

/// Hard-delete a single workspace and all its data in FK-safe order.
/// Called by the background cron task after the grace period expires.
pub async fn hard_delete_workspace(pool: &PgPool, workspace_id: i64) {
    let result: Result<(), sqlx::Error> = async {
        let mut tx = pool.begin().await?;

        sqlx::query(
            "UPDATE sessions SET revoked_at = NOW() \
             WHERE user_id IN ( \
                 SELECT user_id FROM workspace_members WHERE workspace_id = $1 \
             ) AND revoked_at IS NULL",
        )
        .bind(workspace_id)
        .execute(&mut *tx)
        .await?;

        sqlx::query(
            "DELETE FROM entity_settings \
             WHERE scope = 'workspace' AND scope_id = $1::text",
        )
        .bind(workspace_id)
        .execute(&mut *tx)
        .await?;

        sqlx::query(
            "DELETE FROM storage_quotas \
             WHERE scope = 'workspace' AND scope_id = $1::text",
        )
        .bind(workspace_id)
        .execute(&mut *tx)
        .await?;

        sqlx::query(
            "DELETE FROM lookup_values \
             WHERE workspace_id = $1",
        )
        .bind(workspace_id)
        .execute(&mut *tx)
        .await?;

        sqlx::query("DELETE FROM workspaces WHERE id = $1")
            .bind(workspace_id)
            .execute(&mut *tx)
            .await?;

        tx.commit().await?;
        Ok(())
    }
    .await;

    match result {
        Ok(_) => tracing::info!(workspace_id, "Hard-deleted workspace"),
        Err(e) => tracing::error!(workspace_id, error = ?e, "Failed to hard-delete workspace"),
    }
}
