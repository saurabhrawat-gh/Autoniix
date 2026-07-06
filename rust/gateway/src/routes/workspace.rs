use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use chrono::{DateTime, Utc};
use rand::distributions::Alphanumeric;
use rand::Rng;
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    email::{fire_workspace_deletion_emails, DeletionEmailEvent},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // ── admin workspace lifecycle ────────────────────────────────────────
        .route("/api/v2/workspaces/:id", delete(delete_workspace))
        .route(
            "/api/v2/workspaces/:id/cancel-deletion",
            post(cancel_deletion),
        )
        .route(
            "/api/v2/workspaces/:id/deletion-status",
            get(deletion_status),
        )
        // ── user-facing workspace (current workspace from JWT) ───────────────
        .route(
            "/api/v2/workspace",
            get(get_workspace).put(update_workspace),
        )
        // ── members ─────────────────────────────────────────────────────────
        .route("/api/v2/workspace/members", get(list_members))
        .route(
            "/api/v2/workspace/members/:user_id/role",
            put(set_member_role),
        )
        .route("/api/v2/workspace/members/:user_id", delete(remove_member))
        // ── invites ──────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/invites",
            get(list_invites).post(create_invite),
        )
        .route(
            "/api/v2/workspace/invites/:invite_id",
            delete(revoke_invite),
        )
        // ── brands ───────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/brands",
            get(list_brands).post(create_brand),
        )
        .route(
            "/api/v2/workspace/brands/:brand_id",
            get(get_brand).put(update_brand),
        )
        // ── series ───────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/series",
            get(list_series).post(create_series),
        )
        .route(
            "/api/v2/workspace/series/:series_id",
            put(update_series).delete(delete_series),
        )
        // ── campaigns ────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/campaigns",
            get(list_campaigns).post(create_campaign),
        )
        .route(
            "/api/v2/workspace/campaigns/:campaign_id",
            put(update_campaign),
        )
        // ── projects ─────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/projects",
            get(list_projects).post(create_project),
        )
        .route(
            "/api/v2/workspace/projects/:project_id",
            get(get_project).put(update_project).delete(delete_project),
        )
        // ── settings ─────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/settings",
            get(get_settings).put(upsert_setting),
        )
        // ── integrations ─────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/integrations",
            get(get_integrations).put(update_integrations),
        )
        // ── ownership ────────────────────────────────────────────────────────
        .route(
            "/api/v2/workspace/transfer-ownership",
            post(transfer_ownership),
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
#[utoipa::path(
    delete,
    path = "/api/v2/workspaces/{id}",
    tag = "workspace",
    params(("id" = i64, Path, description = "Workspace id")),
    responses(
        (status = 200, description = "Workspace scheduled for deletion"),
        (status = 400, description = "Last workspace or invalid state"),
        (status = 404, description = "Workspace not found"),
        (status = 409, description = "Already pending deletion"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn delete_workspace(
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

    #[allow(clippy::type_complexity)]
    let row: Option<(Option<DateTime<Utc>>, String, i64, String)> = sqlx::query_as(
        "SELECT deleted_at, status, owner_user_id, name FROM workspaces WHERE id = $1",
    )
    .bind(workspace_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let (deleted_at, _status, owner_user_id, workspace_name) = match row {
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

    fire_workspace_deletion_emails(
        pool.clone(),
        workspace_id,
        workspace_name,
        DeletionEmailEvent::SoftDelete,
        Some(chrono::Utc::now() + chrono::Duration::days(grace_days)),
    );

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
#[utoipa::path(
    post,
    path = "/api/v2/workspaces/{id}/cancel-deletion",
    tag = "workspace",
    params(("id" = i64, Path, description = "Workspace id")),
    responses(
        (status = 200, description = "Deletion cancelled"),
        (status = 404, description = "Workspace not found"),
        (status = 410, description = "Grace period expired"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn cancel_deletion(
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
    let row: Option<(
        Option<DateTime<Utc>>,
        Option<DateTime<Utc>>,
        String,
        i64,
        String,
    )> = sqlx::query_as(
        "SELECT deleted_at, delete_scheduled_at, status, owner_user_id, name \
             FROM workspaces WHERE id = $1",
    )
    .bind(workspace_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let (deleted_at, delete_scheduled_at, status, owner_user_id, workspace_name) = match row {
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

    fire_workspace_deletion_emails(
        pool.clone(),
        workspace_id,
        workspace_name,
        DeletionEmailEvent::Cancelled,
        None,
    );

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
#[utoipa::path(
    get,
    path = "/api/v2/workspaces/{id}/deletion-status",
    tag = "workspace",
    params(("id" = i64, Path, description = "Workspace id")),
    responses(
        (status = 200, description = "Deletion status"),
        (status = 404, description = "Workspace not found"),
    ),
    security(("cookie_auth" = []))
)]
pub(crate) async fn deletion_status(
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

// ═══════════════════════════════════════════════════════════════════════════
//  User-facing workspace: GET/PUT /api/v2/workspace
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize, Default)]
struct UpdateWorkspaceIn {
    name: Option<String>,
    timezone: Option<String>,
    logo_url: Option<String>,
    monthly_budget_usd: Option<f64>,
}

pub(crate) async fn get_workspace(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let row = sqlx::query!(
        r#"SELECT id, name, slug, plan, owner_user_id, billing_email,
                  monthly_budget_usd::float8 AS "monthly_budget_usd: f64", timezone, logo_url, settings, created_at, updated_at
             FROM workspaces WHERE id = $1"#,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::NotFound("workspace".into()))?;

    Ok(Json(json!({
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "plan": row.plan,
        "owner_user_id": row.owner_user_id,
        "billing_email": row.billing_email,
        "monthly_budget_usd": row.monthly_budget_usd,
        "timezone": row.timezone,
        "logo_url": row.logo_url,
        "settings": row.settings,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    })))
}

pub(crate) async fn update_workspace(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<UpdateWorkspaceIn>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can update workspace".into(),
        ));
    }
    sqlx::query!(
        r#"UPDATE workspaces
              SET name = COALESCE($1, name),
                  timezone = COALESCE($2, timezone),
                  logo_url = COALESCE($3, logo_url),
                  monthly_budget_usd = COALESCE($4::float8, monthly_budget_usd),
                  updated_at = NOW()
            WHERE id = $5"#,
        body.name,
        body.timezone,
        body.logo_url,
        body.monthly_budget_usd,
        principal.wid
    )
    .execute(&pool)
    .await?;
    get_workspace(AuthUser(principal), State(pool)).await
}

// ═══════════════════════════════════════════════════════════════════════════
//  Members
// ═══════════════════════════════════════════════════════════════════════════

pub(crate) async fn list_members(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT wm.user_id, wm.role, wm.joined_at,
                  u.email, u.display_name
             FROM workspace_members wm
             JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = $1
            ORDER BY wm.joined_at"#,
        principal.wid
    )
    .fetch_all(&pool)
    .await?;

    let members: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "user_id": r.user_id,
                "email": r.email,
                "display_name": r.display_name,
                "role": r.role,
                "joined_at": r.joined_at,
            })
        })
        .collect();
    Ok(Json(json!({ "members": members })))
}

#[derive(Deserialize)]
struct SetRoleIn {
    role: String,
}

pub(crate) async fn set_member_role(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(target_user_id): Path<i64>,
    Json(body): Json<SetRoleIn>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can change roles".into(),
        ));
    }
    let valid_roles = [
        "owner", "admin", "producer", "editor", "reviewer", "analyst", "viewer",
    ];
    if !valid_roles.contains(&body.role.as_str()) {
        return Err(ApiError::Validation(format!("invalid role: {}", body.role)));
    }
    let updated = sqlx::query!(
        r#"UPDATE workspace_members SET role = $1
            WHERE workspace_id = $2 AND user_id = $3"#,
        body.role,
        principal.wid,
        target_user_id
    )
    .execute(&pool)
    .await?;
    if updated.rows_affected() == 0 {
        return Err(ApiError::NotFound("member".into()));
    }
    Ok(Json(json!({ "ok": true })))
}

pub(crate) async fn remove_member(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(target_user_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can remove members".into(),
        ));
    }
    let my_user_id: i64 = principal.user_id.parse().unwrap_or(0);
    if target_user_id == my_user_id {
        return Err(ApiError::Validation("cannot remove yourself".into()));
    }
    sqlx::query!(
        "DELETE FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        principal.wid,
        target_user_id
    )
    .execute(&pool)
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

// ═══════════════════════════════════════════════════════════════════════════
//  Invitations
// ═══════════════════════════════════════════════════════════════════════════

pub(crate) async fn list_invites(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT id, email, role, accepted_at, expires_at, created_at
             FROM workspace_invitations
            WHERE workspace_id = $1 AND accepted_at IS NULL AND expires_at > NOW()
            ORDER BY created_at DESC"#,
        principal.wid
    )
    .fetch_all(&pool)
    .await?;

    let invites: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id,
                "email": r.email,
                "role": r.role,
                "accepted_at": r.accepted_at,
                "expires_at": r.expires_at,
                "created_at": r.created_at,
            })
        })
        .collect();
    Ok(Json(json!({ "invites": invites })))
}

#[derive(Deserialize)]
struct CreateInviteIn {
    email: String,
    role: Option<String>,
}

pub(crate) async fn create_invite(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateInviteIn>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can invite members".into(),
        ));
    }
    let role = body.role.unwrap_or_else(|| "viewer".to_string());
    let token: String = rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(48)
        .map(char::from)
        .collect();
    let mut hasher = Sha256::new();
    hasher.update(token.as_bytes());
    let token_hash = format!("{:x}", hasher.finalize());
    let inviter_id: i64 = principal.user_id.parse().unwrap_or(0);
    let expires_at = chrono::Utc::now() + chrono::Duration::days(7);

    let row = sqlx::query!(
        r#"INSERT INTO workspace_invitations (workspace_id, email, role, token_hash, invited_by, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (token_hash) DO NOTHING
               RETURNING id, email, role, expires_at, created_at"#,
        principal.wid,
        body.email.to_lowercase(),
        role,
        token_hash,
        inviter_id,
        expires_at
    )
    .fetch_one(&pool)
    .await?;

    Ok(Json(json!({
        "id": row.id,
        "email": row.email,
        "role": row.role,
        "token": token,
        "expires_at": row.expires_at,
        "created_at": row.created_at,
    })))
}

pub(crate) async fn revoke_invite(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(invite_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can revoke invites".into(),
        ));
    }
    let deleted = sqlx::query!(
        "DELETE FROM workspace_invitations WHERE id = $1 AND workspace_id = $2",
        invite_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    if deleted.rows_affected() == 0 {
        return Err(ApiError::NotFound("invite".into()));
    }
    Ok(StatusCode::NO_CONTENT)
}

// ═══════════════════════════════════════════════════════════════════════════
//  Brands
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize)]
struct CreateBrandIn {
    name: String,
    slug: Option<String>,
    description: Option<String>,
    legal_name: Option<String>,
    website: Option<String>,
    primary_color: Option<String>,
    secondary_color: Option<String>,
    logo_url: Option<String>,
    voice_summary: Option<String>,
}

#[derive(Deserialize)]
struct UpdateBrandIn {
    name: Option<String>,
    description: Option<String>,
    legal_name: Option<String>,
    website: Option<String>,
    primary_color: Option<String>,
    secondary_color: Option<String>,
    logo_url: Option<String>,
    voice_summary: Option<String>,
}

pub(crate) async fn list_brands(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT id, name, slug, description, legal_name, website,
                  primary_color, secondary_color, logo_url, voice_summary,
                  created_at, updated_at
             FROM brands WHERE workspace_id = $1
             ORDER BY created_at"#,
        principal.wid
    )
    .fetch_all(&pool)
    .await?;

    let brands: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "name": r.name, "slug": r.slug,
                "description": r.description, "legal_name": r.legal_name,
                "website": r.website, "primary_color": r.primary_color,
                "secondary_color": r.secondary_color, "logo_url": r.logo_url,
                "voice_summary": r.voice_summary,
                "created_at": r.created_at, "updated_at": r.updated_at,
            })
        })
        .collect();
    Ok(Json(json!({ "brands": brands })))
}

pub(crate) async fn create_brand(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateBrandIn>,
) -> ApiResult<impl IntoResponse> {
    let slug = body
        .slug
        .unwrap_or_else(|| body.name.to_lowercase().replace(' ', "-"));
    let creator_id: i64 = principal.user_id.parse().unwrap_or(0);
    let row = sqlx::query!(
        r#"INSERT INTO brands (workspace_id, name, slug, description, legal_name, website,
                               primary_color, secondary_color, logo_url, voice_summary, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
               RETURNING id, name, slug, created_at"#,
        principal.wid,
        body.name,
        slug,
        body.description,
        body.legal_name,
        body.website,
        body.primary_color,
        body.secondary_color,
        body.logo_url,
        body.voice_summary,
        creator_id
    )
    .fetch_one(&pool)
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(
            json!({ "id": row.id, "name": row.name, "slug": row.slug, "created_at": row.created_at }),
        ),
    ))
}

pub(crate) async fn get_brand(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(brand_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let row = sqlx::query!(
        r#"SELECT id, name, slug, description, legal_name, website,
                  primary_color, secondary_color, logo_url, voice_summary,
                  created_at, updated_at
             FROM brands WHERE id = $1 AND workspace_id = $2"#,
        brand_id,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::NotFound("brand".into()))?;

    Ok(Json(json!({
        "id": row.id, "name": row.name, "slug": row.slug,
        "description": row.description, "legal_name": row.legal_name,
        "website": row.website, "primary_color": row.primary_color,
        "secondary_color": row.secondary_color, "logo_url": row.logo_url,
        "voice_summary": row.voice_summary,
        "created_at": row.created_at, "updated_at": row.updated_at,
    })))
}

pub(crate) async fn update_brand(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(brand_id): Path<i64>,
    Json(body): Json<UpdateBrandIn>,
) -> ApiResult<impl IntoResponse> {
    let updated = sqlx::query!(
        r#"UPDATE brands
              SET name = COALESCE($1, name),
                  description = COALESCE($2, description),
                  legal_name = COALESCE($3, legal_name),
                  website = COALESCE($4, website),
                  primary_color = COALESCE($5, primary_color),
                  secondary_color = COALESCE($6, secondary_color),
                  logo_url = COALESCE($7, logo_url),
                  voice_summary = COALESCE($8, voice_summary),
                  updated_at = NOW()
            WHERE id = $9 AND workspace_id = $10"#,
        body.name,
        body.description,
        body.legal_name,
        body.website,
        body.primary_color,
        body.secondary_color,
        body.logo_url,
        body.voice_summary,
        brand_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    if updated.rows_affected() == 0 {
        return Err(ApiError::NotFound("brand".into()));
    }
    get_brand(AuthUser(principal), State(pool), Path(brand_id)).await
}

// ═══════════════════════════════════════════════════════════════════════════
//  Series
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize)]
struct CreateSeriesIn {
    channel_id: String,
    name: String,
    description: Option<String>,
    format: Option<String>,
    target_duration_s: Option<i32>,
    cadence: Option<String>,
    thumbnail_style: Option<String>,
}

#[derive(Deserialize)]
struct UpdateSeriesIn {
    name: Option<String>,
    description: Option<String>,
    format: Option<String>,
    target_duration_s: Option<i32>,
    cadence: Option<String>,
    thumbnail_style: Option<String>,
}

pub(crate) async fn list_series(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT s.id, s.channel_id, s.name, s.description, s.format,
                  s.target_duration_s, s.cadence, s.thumbnail_style
             FROM series s
             JOIN channels c ON c.channel_id = s.channel_id
            WHERE c.workspace_id = $1
            ORDER BY s.id"#,
        principal.wid
    )
    .fetch_all(&pool)
    .await?;
    let items: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "channel_id": r.channel_id, "name": r.name,
                "description": r.description, "format": r.format,
                "target_duration_s": r.target_duration_s, "cadence": r.cadence,
                "thumbnail_style": r.thumbnail_style,
            })
        })
        .collect();
    Ok(Json(json!({ "series": items })))
}

pub(crate) async fn create_series(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateSeriesIn>,
) -> ApiResult<impl IntoResponse> {
    let channel_check = sqlx::query_scalar!(
        "SELECT 1 FROM channels WHERE channel_id = $1 AND workspace_id = $2",
        body.channel_id,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?;
    if channel_check.is_none() {
        return Err(ApiError::NotFound("channel".into()));
    }
    let row = sqlx::query!(
        r#"INSERT INTO series (channel_id, name, description, format, target_duration_s, cadence, thumbnail_style)
               VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id, name"#,
        body.channel_id,
        body.name,
        body.description,
        body.format,
        body.target_duration_s,
        body.cadence,
        body.thumbnail_style
    )
    .fetch_one(&pool)
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({ "id": row.id, "name": row.name })),
    ))
}

pub(crate) async fn update_series(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(series_id): Path<i64>,
    Json(body): Json<UpdateSeriesIn>,
) -> ApiResult<impl IntoResponse> {
    let updated = sqlx::query!(
        r#"UPDATE series s
              SET name = COALESCE($1, s.name),
                  description = COALESCE($2, s.description),
                  format = COALESCE($3, s.format),
                  target_duration_s = COALESCE($4, s.target_duration_s),
                  cadence = COALESCE($5, s.cadence),
                  thumbnail_style = COALESCE($6, s.thumbnail_style)
             FROM channels c
            WHERE s.id = $7 AND s.channel_id = c.channel_id AND c.workspace_id = $8"#,
        body.name,
        body.description,
        body.format,
        body.target_duration_s,
        body.cadence,
        body.thumbnail_style,
        series_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    if updated.rows_affected() == 0 {
        return Err(ApiError::NotFound("series".into()));
    }
    Ok(Json(json!({ "ok": true })))
}

pub(crate) async fn delete_series(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(series_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query!(
        r#"DELETE FROM series s USING channels c
            WHERE s.id = $1 AND s.channel_id = c.channel_id AND c.workspace_id = $2"#,
        series_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

// ═══════════════════════════════════════════════════════════════════════════
//  Campaigns
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize)]
struct ListCampaignsQuery {
    brand_id: Option<i64>,
}

#[derive(Deserialize)]
struct CreateCampaignIn {
    brand_id: i64,
    name: String,
    description: Option<String>,
    theme: Option<String>,
    start_at: Option<DateTime<Utc>>,
    end_at: Option<DateTime<Utc>>,
}

#[derive(Deserialize)]
struct UpdateCampaignIn {
    name: Option<String>,
    description: Option<String>,
    theme: Option<String>,
    status: Option<String>,
    start_at: Option<DateTime<Utc>>,
    end_at: Option<DateTime<Utc>>,
}

pub(crate) async fn list_campaigns(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListCampaignsQuery>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT c.id, c.brand_id, c.name, c.description, c.theme,
                  c.start_at, c.end_at, c.status, c.created_at
             FROM campaigns c
             JOIN brands b ON b.id = c.brand_id
            WHERE b.workspace_id = $1
              AND ($2::BIGINT IS NULL OR c.brand_id = $2)
            ORDER BY c.created_at DESC"#,
        principal.wid,
        q.brand_id
    )
    .fetch_all(&pool)
    .await?;
    let items: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "brand_id": r.brand_id, "name": r.name,
                "description": r.description, "theme": r.theme,
                "start_at": r.start_at, "end_at": r.end_at,
                "status": r.status, "created_at": r.created_at,
            })
        })
        .collect();
    Ok(Json(json!({ "campaigns": items })))
}

pub(crate) async fn create_campaign(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateCampaignIn>,
) -> ApiResult<impl IntoResponse> {
    let brand_check = sqlx::query_scalar!(
        "SELECT 1 FROM brands WHERE id = $1 AND workspace_id = $2",
        body.brand_id,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?;
    if brand_check.is_none() {
        return Err(ApiError::NotFound("brand".into()));
    }
    let creator_id: i64 = principal.user_id.parse().unwrap_or(0);
    let row = sqlx::query!(
        r#"INSERT INTO campaigns (brand_id, name, description, theme, start_at, end_at, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               RETURNING id, name, status, created_at"#,
        body.brand_id,
        body.name,
        body.description,
        body.theme,
        body.start_at,
        body.end_at,
        creator_id
    )
    .fetch_one(&pool)
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(
            json!({ "id": row.id, "name": row.name, "status": row.status, "created_at": row.created_at }),
        ),
    ))
}

pub(crate) async fn update_campaign(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(campaign_id): Path<i64>,
    Json(body): Json<UpdateCampaignIn>,
) -> ApiResult<impl IntoResponse> {
    let updated = sqlx::query!(
        r#"UPDATE campaigns c
              SET name = COALESCE($1, c.name),
                  description = COALESCE($2, c.description),
                  theme = COALESCE($3, c.theme),
                  status = COALESCE($4, c.status),
                  start_at = COALESCE($5, c.start_at),
                  end_at = COALESCE($6, c.end_at)
             FROM brands b
            WHERE c.id = $7 AND c.brand_id = b.id AND b.workspace_id = $8"#,
        body.name,
        body.description,
        body.theme,
        body.status,
        body.start_at,
        body.end_at,
        campaign_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    if updated.rows_affected() == 0 {
        return Err(ApiError::NotFound("campaign".into()));
    }
    Ok(Json(json!({ "ok": true })))
}

// ═══════════════════════════════════════════════════════════════════════════
//  Projects
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize, Default)]
struct ListProjectsQuery {
    channel_id: Option<String>,
    status: Option<String>,
    limit: Option<i64>,
}

#[derive(Deserialize)]
struct CreateProjectIn {
    channel_id: String,
    title: String,
    brief: Option<String>,
    series_id: Option<i64>,
    campaign_id: Option<i64>,
    priority: Option<i16>,
    target_publish_at: Option<DateTime<Utc>>,
    tags: Option<Vec<String>>,
    estimated_cost_usd: Option<f64>,
}

#[derive(Deserialize)]
struct UpdateProjectIn {
    title: Option<String>,
    brief: Option<String>,
    status: Option<String>,
    priority: Option<i16>,
    target_publish_at: Option<DateTime<Utc>>,
    estimated_cost_usd: Option<f64>,
}

pub(crate) async fn list_projects(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListProjectsQuery>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT p.id, p.channel_id, p.title, p.brief, p.status, p.priority,
                  p.target_publish_at, p.tags, p.estimated_cost_usd::float8 AS "estimated_cost_usd: f64",
                  p.series_id, p.campaign_id
             FROM projects p
             JOIN channels c ON c.channel_id = p.channel_id
            WHERE c.workspace_id = $1
              AND ($2::VARCHAR IS NULL OR p.channel_id = $2)
              AND ($3::VARCHAR IS NULL OR p.status = $3)
            ORDER BY p.priority DESC, p.id DESC
            LIMIT $4"#,
        principal.wid,
        q.channel_id,
        q.status,
        q.limit.unwrap_or(100)
    )
    .fetch_all(&pool)
    .await?;
    let items: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id, "channel_id": r.channel_id, "title": r.title,
                "brief": r.brief, "status": r.status, "priority": r.priority,
                "target_publish_at": r.target_publish_at,
                "tags": r.tags, "estimated_cost_usd": r.estimated_cost_usd,
                "series_id": r.series_id, "campaign_id": r.campaign_id,
            })
        })
        .collect();
    Ok(Json(json!({ "projects": items })))
}

pub(crate) async fn create_project(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CreateProjectIn>,
) -> ApiResult<impl IntoResponse> {
    let channel_check = sqlx::query_scalar!(
        "SELECT 1 FROM channels WHERE channel_id = $1 AND workspace_id = $2",
        body.channel_id,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?;
    if channel_check.is_none() {
        return Err(ApiError::NotFound("channel".into()));
    }
    let tags = body.tags.unwrap_or_default();
    let row = sqlx::query!(
        r#"INSERT INTO projects
               (channel_id, title, brief, series_id, campaign_id, priority,
                target_publish_at, tags, estimated_cost_usd)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::float8)
               RETURNING id, title, status"#,
        body.channel_id,
        body.title,
        body.brief,
        body.series_id,
        body.campaign_id,
        body.priority.unwrap_or(5),
        body.target_publish_at,
        &tags,
        body.estimated_cost_usd
    )
    .fetch_one(&pool)
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({ "id": row.id, "title": row.title, "status": row.status })),
    ))
}

pub(crate) async fn get_project(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(project_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let row = sqlx::query!(
        r#"SELECT p.id, p.channel_id, p.title, p.brief, p.status, p.priority,
                  p.target_publish_at, p.tags, p.estimated_cost_usd::float8 AS "estimated_cost_usd: f64",
                  p.series_id, p.campaign_id
             FROM projects p
             JOIN channels c ON c.channel_id = p.channel_id
            WHERE p.id = $1 AND c.workspace_id = $2"#,
        project_id,
        principal.wid
    )
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::NotFound("project".into()))?;

    Ok(Json(json!({
        "id": row.id, "channel_id": row.channel_id, "title": row.title,
        "brief": row.brief, "status": row.status, "priority": row.priority,
        "target_publish_at": row.target_publish_at,
        "tags": row.tags, "estimated_cost_usd": row.estimated_cost_usd,
        "series_id": row.series_id, "campaign_id": row.campaign_id,
    })))
}

pub(crate) async fn update_project(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(project_id): Path<i64>,
    Json(body): Json<UpdateProjectIn>,
) -> ApiResult<impl IntoResponse> {
    let updated = sqlx::query!(
        r#"UPDATE projects p
              SET title = COALESCE($1, p.title),
                  brief = COALESCE($2, p.brief),
                  status = COALESCE($3, p.status),
                  priority = COALESCE($4, p.priority),
                  target_publish_at = COALESCE($5, p.target_publish_at),
                  estimated_cost_usd = COALESCE($6::float8, p.estimated_cost_usd)
             FROM channels c
            WHERE p.id = $7 AND p.channel_id = c.channel_id AND c.workspace_id = $8"#,
        body.title,
        body.brief,
        body.status,
        body.priority,
        body.target_publish_at,
        body.estimated_cost_usd,
        project_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    if updated.rows_affected() == 0 {
        return Err(ApiError::NotFound("project".into()));
    }
    get_project(AuthUser(principal), State(pool), Path(project_id)).await
}

pub(crate) async fn delete_project(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(project_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query!(
        r#"DELETE FROM projects p USING channels c
            WHERE p.id = $1 AND p.channel_id = c.channel_id AND c.workspace_id = $2"#,
        project_id,
        principal.wid
    )
    .execute(&pool)
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

// ═══════════════════════════════════════════════════════════════════════════
//  Settings (entity_settings for workspace scope)
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize, Default)]
struct GetSettingsQuery {
    key: Option<String>,
}

#[derive(Deserialize)]
struct UpsertSettingIn {
    key: String,
    value: Value,
}

pub(crate) async fn get_settings(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<GetSettingsQuery>,
) -> ApiResult<impl IntoResponse> {
    let scope_id = principal.wid.to_string();
    let rows = sqlx::query!(
        r#"SELECT key, value, locked FROM entity_settings
            WHERE scope = 'workspace' AND scope_id = $1
              AND ($2::TEXT IS NULL OR key = $2)
            ORDER BY key"#,
        scope_id,
        q.key
    )
    .fetch_all(&pool)
    .await?;
    let settings: Vec<Value> = rows
        .into_iter()
        .map(|r| json!({ "key": r.key, "value": r.value, "locked": r.locked }))
        .collect();
    Ok(Json(json!({ "settings": settings })))
}

pub(crate) async fn upsert_setting(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<UpsertSettingIn>,
) -> ApiResult<impl IntoResponse> {
    let scope_id = principal.wid.to_string();
    sqlx::query!(
        r#"INSERT INTO entity_settings (scope, scope_id, key, value)
               VALUES ('workspace', $1, $2, $3)
               ON CONFLICT (scope, scope_id, key)
               DO UPDATE SET value = EXCLUDED.value"#,
        scope_id,
        body.key,
        body.value
    )
    .execute(&pool)
    .await?;
    Ok(Json(json!({ "ok": true, "key": body.key })))
}

// ═══════════════════════════════════════════════════════════════════════════
//  Integrations (stored in workspaces.settings JSONB)
// ═══════════════════════════════════════════════════════════════════════════

pub(crate) async fn get_integrations(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let row = sqlx::query_scalar!(
        "SELECT settings->'integrations' FROM workspaces WHERE id = $1",
        principal.wid
    )
    .fetch_optional(&pool)
    .await?
    .unwrap_or(None)
    .unwrap_or(Value::Object(serde_json::Map::new()));
    Ok(Json(json!({ "integrations": row })))
}

#[derive(Deserialize)]
struct UpdateIntegrationsIn {
    integrations: Value,
}

pub(crate) async fn update_integrations(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<UpdateIntegrationsIn>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" && principal.global_role != "superadmin" {
        return Err(ApiError::ForbiddenWith(
            "only owner can update integrations".into(),
        ));
    }
    sqlx::query!(
        r#"UPDATE workspaces
              SET settings = jsonb_set(settings, '{integrations}', $1, true),
                  updated_at = NOW()
            WHERE id = $2"#,
        body.integrations,
        principal.wid
    )
    .execute(&pool)
    .await?;
    Ok(Json(json!({ "ok": true })))
}

// ═══════════════════════════════════════════════════════════════════════════
//  Transfer ownership
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Deserialize)]
struct TransferOwnershipIn {
    new_owner_user_id: i64,
}

pub(crate) async fn transfer_ownership(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<TransferOwnershipIn>,
) -> ApiResult<impl IntoResponse> {
    if principal.role != "owner" {
        return Err(ApiError::ForbiddenWith(
            "only owner can transfer ownership".into(),
        ));
    }
    let my_id: i64 = principal.user_id.parse().unwrap_or(0);
    if body.new_owner_user_id == my_id {
        return Err(ApiError::Validation("cannot transfer to yourself".into()));
    }
    let member_check = sqlx::query_scalar!(
        "SELECT 1 FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        principal.wid,
        body.new_owner_user_id
    )
    .fetch_optional(&pool)
    .await?;
    if member_check.is_none() {
        return Err(ApiError::NotFound(
            "new owner must be a workspace member".into(),
        ));
    }

    let mut tx = pool.begin().await?;
    sqlx::query!(
        "UPDATE workspace_members SET role = 'owner' WHERE workspace_id = $1 AND user_id = $2",
        principal.wid,
        body.new_owner_user_id
    )
    .execute(&mut *tx)
    .await?;
    sqlx::query!(
        "UPDATE workspace_members SET role = 'admin' WHERE workspace_id = $1 AND user_id = $2",
        principal.wid,
        my_id
    )
    .execute(&mut *tx)
    .await?;
    sqlx::query!(
        "UPDATE workspaces SET owner_user_id = $1 WHERE id = $2",
        body.new_owner_user_id,
        principal.wid
    )
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;

    Ok(Json(
        json!({ "ok": true, "new_owner_user_id": body.new_owner_user_id }),
    ))
}
