//! Provider/API management — native Rust port of `src/services/dashboard/v2/providers.py`.
//!
//! All endpoints are handled natively with Postgres. The Python proxy fallback
//! has been removed. Credential secret management uses vault_path (caller-owned)
//! or secret_blob (base64-stored) depending on PROVIDERS_SECRET_BACKEND.

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, patch, post, put},
    Json, Router,
};
use chrono::Utc;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::Principal,
};

// ─── Route registration ─────────────────────────────────────────────────────

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // ── Read endpoints ──────────────────────────────────────────────────
        .route("/api/v2/providers/categories",            get(list_categories))
        .route("/api/v2/providers/kinds",                 get(list_kinds))
        .route("/api/v2/providers/content-modes",         get(list_content_modes))
        .route("/api/v2/providers/credentials",           get(list_credentials))
        .route("/api/v2/providers/credentials/rotation-status", get(all_rotation_status))
        .route("/api/v2/providers/credentials/:id/rotation-status", get(credential_rotation_status))
        .route("/api/v2/providers/chains",                get(list_chains))
        .route("/api/v2/providers/chains/:category",      get(get_chain))
        .route("/api/v2/providers/resolved",              get(resolved_chain))
        .route("/api/v2/providers/marketplace",           get(list_marketplace))
        .route("/api/v2/providers/catalog-for-category",  get(catalog_for_category))
        .route("/api/v2/providers/setup-checklist",       get(setup_checklist))
        .route("/api/v2/providers/routes",                get(list_routes))
        .route("/api/v2/providers/quotas",                get(list_quotas))
        .route("/api/v2/providers/audit-log",             get(list_audit_log))
        .route("/api/v2/providers/health/:credential_id", get(credential_health))
        .route("/api/v2/providers/sandbox/runs",          get(sandbox_runs))
        // ── Simple mutation endpoints ────────────────────────────────────────
        .route("/api/v2/providers/restore-defaults",      post(restore_defaults))
        .route("/api/v2/providers/kinds/:kind",           delete(delete_kind))
        .route("/api/v2/providers/categories",            post(create_category))
        .route("/api/v2/providers/categories/:name",      patch(rename_category).delete(delete_category))
        .route("/api/v2/providers/chains/:category",      put(set_chain))
        .route("/api/v2/providers/chains",                put(upsert_chain_v2).delete(delete_chain))
        .route("/api/v2/providers/chains/reorder",        patch(reorder_chains))
        .route("/api/v2/providers/credentials/:id/enabled",        put(set_credential_enabled))
        .route("/api/v2/providers/credentials/:id/default-fallback",
            put(set_default_fallback).delete(clear_default_fallback))
        .route("/api/v2/providers/chains/entry/:entry_id/enabled", put(set_chain_entry_enabled))
        .route("/api/v2/providers/marketplace",           post(create_marketplace_provider))
        .route("/api/v2/providers/marketplace/:provider_key", delete(delete_marketplace_provider))
        .route("/api/v2/providers/routes/:category",      put(upsert_route))
        .route("/api/v2/providers/quotas",                post(create_quota))
        .route("/api/v2/providers/quotas/:quota_id",      put(update_quota).delete(delete_quota))
        // ── Credential CRUD + lifecycle ─────────────────────────────────────
        .route("/api/v2/providers/credentials",           post(create_credential))
        .route("/api/v2/providers/credentials/:id",       put(update_credential).delete(delete_credential))
        .route("/api/v2/providers/credentials/:id/test",  post(test_credential))
        .route("/api/v2/providers/credentials/:id/rotate",post(rotate_credential))
        .with_state(pool)
}

// ─── Credential CRUD ─────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct CredentialCreateIn {
    category:       String,
    provider_name:  String,
    label:          String,
    vault_path:     String,
    #[serde(default)] extra_config:   Value,
    #[serde(default)] model:          Option<String>,
    #[serde(default)] channel_id:     Option<String>,
    #[serde(default)] content_mode:   Option<String>,
    #[serde(default)] scope_priority: Option<i16>,
    #[serde(default = "default_true")] enabled: bool,
    #[serde(default)] secret_blob:    Option<String>,
}

async fn create_credential(
    AuthUser(p):  AuthUser,
    State(pool):  State<PgPool>,
    Json(body):   Json<CredentialCreateIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let extra = if body.extra_config.is_null() { json!({}) } else { body.extra_config.clone() };
    let created_by: Option<i32> = p.user_id.parse().ok();
    let ws_id: i64 = p.wid;

    let row = sqlx::query!(
        r#"INSERT INTO provider_credentials
               (workspace_id, category, provider_name, label, vault_path, extra_config,
                model, channel_id, content_mode, scope_priority, enabled, created_by, secret_blob)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
           RETURNING id, created_at"#,
        ws_id, body.category, body.provider_name, body.label, body.vault_path, extra,
        body.model, body.channel_id, body.content_mode, body.scope_priority, body.enabled,
        created_by, body.secret_blob,
    ).fetch_one(&pool).await.map_err(ApiError::Database)?;

    Ok((StatusCode::CREATED, Json(json!({
        "status": "ok",
        "data": {
            "id": row.id, "category": body.category,
            "provider_name": body.provider_name, "label": body.label,
            "created_at": row.created_at,
        }
    }))))
}

#[derive(Deserialize)]
struct CredentialUpdateIn {
    #[serde(default)] label:          Option<String>,
    #[serde(default)] extra_config:   Option<Value>,
    #[serde(default)] model:          Option<String>,
    #[serde(default)] enabled:        Option<bool>,
    #[serde(default)] vault_path:     Option<String>,
    #[serde(default)] channel_id:     Option<String>,
    #[serde(default)] content_mode:   Option<String>,
    #[serde(default)] scope_priority: Option<i16>,
    #[serde(default)] secret_blob:    Option<String>,
}

async fn update_credential(
    AuthUser(p):  AuthUser,
    State(pool):  State<PgPool>,
    Path(id):     Path<i64>,
    Json(body):   Json<CredentialUpdateIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let ws_id: i64 = p.wid;

    let existing = sqlx::query!(
        "SELECT label, vault_path, extra_config, model, enabled, channel_id, content_mode, scope_priority, secret_blob \
         FROM provider_credentials WHERE id=$1 AND workspace_id=$2",
        id, ws_id,
    ).fetch_optional(&pool).await.map_err(ApiError::Database)?
     .ok_or_else(|| ApiError::NotFound("Credential not found".into()))?;

    let label        = body.label.unwrap_or(existing.label);
    let vault_path   = body.vault_path.unwrap_or(existing.vault_path);
    let extra_config = body.extra_config.unwrap_or(existing.extra_config);
    let model        = body.model.or(existing.model);
    let enabled      = body.enabled.unwrap_or(existing.enabled);
    let channel_id   = body.channel_id.or(existing.channel_id);
    let content_mode = body.content_mode.or(existing.content_mode);
    let scope_prio   = body.scope_priority.or(Some(existing.scope_priority));
    let secret_blob  = body.secret_blob.or(existing.secret_blob);

    sqlx::query!(
        "UPDATE provider_credentials SET label=$2, vault_path=$3, extra_config=$4, model=$5, \
         enabled=$6, channel_id=$7, content_mode=$8, scope_priority=$9, secret_blob=$10, \
         updated_at=NOW() WHERE id=$1 AND workspace_id=$11",
        id, label, vault_path, extra_config, model, enabled, channel_id, content_mode, scope_prio, secret_blob, ws_id,
    ).execute(&pool).await.map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({ "status": "ok", "data": { "id": id } }))))
}

async fn delete_credential(
    AuthUser(p):  AuthUser,
    State(pool):  State<PgPool>,
    Path(id):     Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner(&p)?;
    let ws_id: i64 = p.wid;

    let res = sqlx::query!(
        "DELETE FROM provider_credentials WHERE id=$1 AND workspace_id=$2",
        id, ws_id,
    ).execute(&pool).await.map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Credential not found".into()));
    }
    Ok((StatusCode::OK, Json(json!({ "status": "ok", "data": { "id": id, "deleted": true } }))))
}

async fn test_credential(
    AuthUser(p):  AuthUser,
    State(pool):  State<PgPool>,
    Path(id):     Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let ws_id: i64 = p.wid;

    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM provider_credentials WHERE id=$1 AND workspace_id=$2",
        id, ws_id,
    ).fetch_optional(&pool).await.map_err(ApiError::Database)?;
    if exists.is_none() {
        return Err(ApiError::NotFound("Credential not found".into()));
    }

    sqlx::query!(
        "UPDATE provider_credentials SET last_health_at=NOW(), updated_at=NOW() WHERE id=$1",
        id,
    ).execute(&pool).await.map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({
        "status": "ok",
        "data": { "id": id, "tested_at": Utc::now(), "result": "queued" }
    }))))
}

async fn rotate_credential(
    AuthUser(p):  AuthUser,
    State(pool):  State<PgPool>,
    Path(id):     Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner(&p)?;
    let ws_id: i64 = p.wid;

    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM provider_credentials WHERE id=$1 AND workspace_id=$2",
        id, ws_id,
    ).fetch_optional(&pool).await.map_err(ApiError::Database)?;
    if exists.is_none() {
        return Err(ApiError::NotFound("Credential not found".into()));
    }

    sqlx::query!(
        "UPDATE provider_credentials \
         SET rotated_at=NOW(), rotation_due_at=NOW() + INTERVAL '30 days', updated_at=NOW() \
         WHERE id=$1",
        id,
    ).execute(&pool).await.map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({ "status": "ok", "data": { "id": id, "rotated": true } }))))
}

// ─── Shared helpers ──────────────────────────────────────────────────────────

const ROTATION_WARN_DAYS: i64 = 30;

fn rotation_status_json(
    id: i64,
    label: String,
    category: String,
    provider_name: String,
    rotated_at: Option<chrono::DateTime<Utc>>,
    rotation_hint: Option<String>,
    created_at: chrono::DateTime<Utc>,
) -> Value {
    let anchor = rotated_at.unwrap_or(created_at);
    let days_since = (Utc::now() - anchor).num_days();
    let overdue = days_since >= ROTATION_WARN_DAYS;
    json!({
        "id": id,
        "label": label,
        "category": category,
        "provider_name": provider_name,
        "rotated_at": rotated_at.map(|t| t.to_rfc3339()),
        "rotation_hint": rotation_hint,
        "days_since_rotation": days_since,
        "overdue": overdue,
        "warn_after_days": ROTATION_WARN_DAYS,
    })
}

fn require_owner(p: &Principal) -> ApiResult<()> {
    if p.role == "owner" || p.global_role == "superadmin" {
        Ok(())
    } else {
        Err(ApiError::ForbiddenWith(
            "Owner role required for this operation".into(),
        ))
    }
}

fn require_owner_or_member(p: &Principal) -> ApiResult<()> {
    match p.role.as_str() {
        "owner" | "member" => Ok(()),
        _ if p.global_role == "superadmin" => Ok(()),
        _ => Err(ApiError::ForbiddenWith(
            "Owner or member role required".into(),
        )),
    }
}

// ─── Query param structs ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub(crate) struct CredentialQuery {
    category: Option<String>,
    channel_id: Option<String>,
    content_mode: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct RotationStatusQuery {
    category: Option<String>,
    overdue_only: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ChainQuery {
    scope: Option<String>,
    scope_id: Option<String>,
    content_mode: Option<String>,
    pipeline_mode: Option<String>,
    category: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ResolvedChainQuery {
    category: String,
    channel_id: Option<String>,
    content_mode: Option<String>,
    pipeline_mode: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct AuditLogQuery {
    category: Option<String>,
    credential_id: Option<i64>,
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct HealthQuery {
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ScopeQuery {
    scope: Option<String>,
    scope_id: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct CatalogQuery {
    category: String,
}

#[derive(Debug, Deserialize)]
pub(crate) struct SandboxRunsQuery {
    credential_id: Option<i64>,
    limit: Option<i64>,
}

// ─── Input body structs ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub(crate) struct KindIn {
    label: String,
    kind: Option<String>,
    icon: Option<String>,
    description: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct CategoryIn {
    label: String,
    kind: String,
    name: Option<String>,
    description: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct RenameCategoryIn {
    label: String,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ChainIn {
    credential_ids: Vec<i64>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ChainV2In {
    #[serde(default = "default_workspace_scope")]
    scope: String,
    scope_id: Option<String>,
    content_mode: Option<String>,
    #[serde(default = "default_production")]
    pipeline_mode: String,
    category: String,
    #[serde(default)]
    credential_ids: Vec<i64>,
}

fn default_workspace_scope() -> String { "workspace".into() }
fn default_production() -> String { "production".into() }

#[derive(Debug, Deserialize)]
pub(crate) struct DeleteChainQuery {
    scope: String,
    category: String,
    scope_id: Option<String>,
    content_mode: Option<String>,
    pipeline_mode: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ReorderItem {
    id: i64,
    position: i32,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ReorderIn {
    items: Vec<ReorderItem>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct EnabledIn {
    enabled: bool,
}

#[derive(Debug, Deserialize)]
pub(crate) struct MarketplaceProviderIn {
    display_name: String,
    kind: String,
    provider_key: Option<String>,
    description: Option<String>,
    #[serde(default)]
    supported_models: Vec<String>,
    #[serde(default)]
    has_free_tier: bool,
    cost_unit: Option<String>,
    #[serde(default = "default_true")]
    requires_api_key: bool,
}

fn default_true() -> bool { true }

#[derive(Debug, Deserialize)]
pub(crate) struct RouteIn {
    #[serde(default = "default_balanced")]
    policy: String,
    #[serde(default)]
    custom_rules: Value,
    primary_credential_id: Option<i64>,
    #[serde(default)]
    fallback_chain: Vec<i64>,
    #[serde(default = "default_workspace_scope")]
    scope: String,
    scope_id: Option<String>,
}

fn default_balanced() -> String { "balanced".into() }

#[derive(Debug, Deserialize)]
pub(crate) struct QuotaIn {
    monthly_cap_usd: f64,
    #[serde(default = "default_80")]
    alert_pct: i32,
    #[serde(default)]
    hard_limit: bool,
    #[serde(default = "default_workspace_scope")]
    scope: String,
    scope_id: Option<String>,
    category: Option<String>,
}

fn default_80() -> i32 { 80 }

// ─── Slugify helper (mirrors Python `_slugify`) ───────────────────────────────

fn slugify(text: &str, maxlen: usize) -> String {
    let mut out = String::new();
    let mut prev_sep = false;
    for ch in text.trim().chars() {
        if ch.is_alphanumeric() {
            out.push(ch.to_lowercase().next().unwrap_or(ch));
            prev_sep = false;
        } else if !prev_sep {
            out.push('_');
            prev_sep = true;
        }
    }
    let slug = out.trim_matches('_').to_string();
    let slug = if slug.is_empty() { "custom".to_string() } else { slug };
    slug.chars().take(maxlen).collect()
}

// ─── READ ENDPOINTS ──────────────────────────────────────────────────────────

pub(crate) async fn list_categories(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        "SELECT name, label, kind, description, is_user_defined \
         FROM provider_categories ORDER BY kind, name"
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "name":           r.name,
        "label":          r.label,
        "kind":           r.kind,
        "description":    r.description,
        "is_user_defined": r.is_user_defined,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_kinds(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT k.kind, k.label, k.icon, k.description, k.is_user_defined, k.sort_order,
                  (SELECT COUNT(*) FROM provider_categories c WHERE c.kind = k.kind) AS category_count
             FROM provider_kinds k
            ORDER BY k.sort_order, k.label"#
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "kind":           r.kind,
        "label":          r.label,
        "icon":           r.icon,
        "description":    r.description,
        "is_user_defined": r.is_user_defined,
        "sort_order":     r.sort_order,
        "category_count": r.category_count,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_content_modes(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        "SELECT name, label, description, sort_order, is_system \
         FROM content_modes ORDER BY sort_order, name"
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "name":        r.name,
        "label":       r.label,
        "description": r.description,
        "sort_order":  r.sort_order,
        "is_system":   r.is_system,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_credentials(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<CredentialQuery>,
) -> ApiResult<impl IntoResponse> {
    let ws_id: i64 = p.wid;

    let rows = sqlx::query!(
        r#"SELECT id, category, provider_name, label, vault_path, extra_config,
                  model, is_default_fallback, channel_id, content_mode, scope_priority,
                  workspace_id, enabled, last_health_ok, last_health_at, last_latency_ms,
                  rotated_at, created_at
             FROM provider_credentials
            WHERE workspace_id = $1
              AND ($2::text IS NULL OR category = $2)
              AND ($3::text IS NULL OR channel_id = $3)
              AND ($4::text IS NULL OR content_mode = $4)
            ORDER BY category, scope_priority DESC NULLS LAST, id"#,
        ws_id,
        q.category,
        q.channel_id,
        q.content_mode,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":                 r.id,
        "category":           r.category,
        "provider_name":      r.provider_name,
        "label":              r.label,
        "vault_path":         r.vault_path,
        "extra_config":       r.extra_config,
        "model":              r.model,
        "is_default_fallback": r.is_default_fallback,
        "channel_id":         r.channel_id,
        "content_mode":       r.content_mode,
        "scope_priority":     r.scope_priority,
        "workspace_id":       r.workspace_id,
        "enabled":            r.enabled,
        "last_health_ok":     r.last_health_ok,
        "last_health_at":     r.last_health_at.map(|t| t.to_rfc3339()),
        "last_latency_ms":    r.last_latency_ms,
        "rotated_at":         r.rotated_at.map(|t| t.to_rfc3339()),
        "created_at":         r.created_at.to_rfc3339(),
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn all_rotation_status(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<RotationStatusQuery>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query!(
        r#"SELECT id, label, category, provider_name, rotated_at, rotation_hint, created_at
             FROM provider_credentials
            WHERE ($1::text IS NULL OR category = $1)
            ORDER BY category, id"#,
        q.category,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let mut items: Vec<Value> = rows.iter().map(|r| {
        rotation_status_json(
            r.id, r.label.clone(), r.category.clone(), r.provider_name.clone(),
            r.rotated_at, r.rotation_hint.clone(), r.created_at,
        )
    }).collect();

    if q.overdue_only.unwrap_or(false) {
        items.retain(|v| v["overdue"].as_bool().unwrap_or(false));
    }

    Ok((StatusCode::OK, Json(json!({ "data": items }))))
}

pub(crate) async fn credential_rotation_status(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    let row = sqlx::query!(
        "SELECT id, label, category, provider_name, rotated_at, rotation_hint, created_at \
         FROM provider_credentials WHERE id = $1",
        id
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Credential not found".into()))?;

    Ok((StatusCode::OK, Json(rotation_status_json(
        row.id, row.label, row.category, row.provider_name,
        row.rotated_at, row.rotation_hint, row.created_at,
    ))))
}

pub(crate) async fn get_chain(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(category): Path<String>,
) -> ApiResult<impl IntoResponse> {
    let ws_id: i64 = p.wid;

    let rows = sqlx::query!(
        r#"SELECT c.id, c.position, c.fallback_strategy,
                  COALESCE(c.is_enabled, TRUE) AS is_enabled,
                  pc.id AS credential_id, pc.label, pc.provider_name, pc.model,
                  pc.enabled, pc.last_health_ok, pc.last_health_at,
                  (SELECT kind FROM provider_categories WHERE name = c.category) AS chain_category_kind,
                  (SELECT kind FROM provider_categories WHERE name = pc.category) AS credential_kind
             FROM provider_chains_v2 c
             JOIN provider_credentials pc ON pc.id = c.credential_id
            WHERE c.scope = 'workspace' AND c.scope_id IS NULL
              AND c.content_mode IS NULL AND c.category = $1
              AND c.workspace_id = $2
            ORDER BY c.position"#,
        category, ws_id
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":                  r.id,
        "position":            r.position,
        "fallback_strategy":   r.fallback_strategy,
        "is_enabled":          r.is_enabled,
        "credential_id":       r.credential_id,
        "label":               r.label,
        "provider_name":       r.provider_name,
        "model":               r.model,
        "enabled":             r.enabled,
        "last_health_ok":      r.last_health_ok,
        "last_health_at":      r.last_health_at.map(|t| t.to_rfc3339()),
        "chain_category_kind": r.chain_category_kind,
        "credential_kind":     r.credential_kind,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_chains(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ChainQuery>,
) -> ApiResult<impl IntoResponse> {
    let ws_id: i64 = p.wid;
    let scope = q.scope.as_deref().unwrap_or("workspace");
    let pm = q.pipeline_mode.as_deref().unwrap_or("production");

    let rows = sqlx::query!(
        r#"SELECT c.id, c.scope, c.scope_id, c.content_mode, c.pipeline_mode, c.category,
                  c.position, c.fallback_strategy,
                  COALESCE(c.is_enabled, TRUE) AS is_enabled,
                  pc.id AS credential_id, pc.label, pc.provider_name, pc.model,
                  pc.enabled, pc.last_health_ok, pc.last_health_at,
                  (SELECT kind FROM provider_categories WHERE name = c.category) AS chain_category_kind,
                  (SELECT kind FROM provider_categories WHERE name = pc.category) AS credential_kind
             FROM provider_chains_v2 c
             JOIN provider_credentials pc ON pc.id = c.credential_id
            WHERE c.scope = $1
              AND ($2::text IS NULL AND c.scope_id IS NULL OR c.scope_id = $2)
              AND ($3::text IS NULL AND c.content_mode IS NULL OR c.content_mode = $3)
              AND COALESCE(c.pipeline_mode, 'production') = $4
              AND c.workspace_id = $5
              AND ($6::text IS NULL OR c.category = $6)
            ORDER BY c.category, c.position"#,
        scope, q.scope_id, q.content_mode, pm, ws_id, q.category,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":                  r.id,
        "scope":               r.scope,
        "scope_id":            r.scope_id,
        "content_mode":        r.content_mode,
        "pipeline_mode":       r.pipeline_mode,
        "category":            r.category,
        "position":            r.position,
        "fallback_strategy":   r.fallback_strategy,
        "is_enabled":          r.is_enabled,
        "credential_id":       r.credential_id,
        "label":               r.label,
        "provider_name":       r.provider_name,
        "model":               r.model,
        "enabled":             r.enabled,
        "last_health_ok":      r.last_health_ok,
        "last_health_at":      r.last_health_at.map(|t| t.to_rfc3339()),
        "chain_category_kind": r.chain_category_kind,
        "credential_kind":     r.credential_kind,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn resolved_chain(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ResolvedChainQuery>,
) -> ApiResult<impl IntoResponse> {
    let pm = q.pipeline_mode.as_deref().unwrap_or("production");

    let mut layers: Vec<(&str, Option<&str>, Option<&str>, &str)> = Vec::new();
    if let Some(cid) = q.channel_id.as_deref() {
        if let Some(cm) = q.content_mode.as_deref() {
            layers.push(("channel", Some(cid), Some(cm), "channel+mode"));
        }
        layers.push(("channel", Some(cid), None, "channel"));
    }
    if let Some(cm) = q.content_mode.as_deref() {
        layers.push(("workspace", None, Some(cm), "workspace+mode"));
    }
    layers.push(("workspace", None, None, "workspace"));
    layers.push(("system", None, None, "system"));

    let mut seen: std::collections::HashSet<i64> = std::collections::HashSet::new();
    let mut out: Vec<Value> = Vec::new();

    for (scope, sid, mode, origin) in &layers {
        let rows = sqlx::query!(
            r#"SELECT c.id AS chain_entry_id, c.position, c.fallback_strategy,
                      COALESCE(c.is_enabled, TRUE) AS is_enabled,
                      pc.id AS credential_id, pc.label, pc.provider_name,
                      pc.model, pc.enabled, pc.last_health_ok
                 FROM provider_chains_v2 c
                 JOIN provider_credentials pc ON pc.id = c.credential_id
                WHERE c.scope = $1
                  AND ($2::text IS NULL AND c.scope_id IS NULL OR c.scope_id = $2)
                  AND ($3::text IS NULL AND c.content_mode IS NULL OR c.content_mode = $3)
                  AND c.category = $4
                  AND COALESCE(c.pipeline_mode, 'production') = $5
                  AND pc.enabled = TRUE
                  AND COALESCE(c.is_enabled, TRUE) = TRUE
                ORDER BY c.position"#,
            scope, sid.map(str::to_string), mode.map(str::to_string), q.category, pm,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

        for r in &rows {
            if seen.contains(&r.credential_id) { continue; }
            seen.insert(r.credential_id);
            out.push(json!({
                "chain_entry_id":    r.chain_entry_id,
                "position":          r.position,
                "fallback_strategy": r.fallback_strategy,
                "is_enabled":        r.is_enabled,
                "credential_id":     r.credential_id,
                "label":             r.label,
                "provider_name":     r.provider_name,
                "model":             r.model,
                "enabled":           r.enabled,
                "last_health_ok":    r.last_health_ok,
                "origin":            origin,
            }));
        }
    }

    let fb = sqlx::query!(
        r#"SELECT id AS credential_id, label, provider_name, model, enabled, last_health_ok
             FROM provider_credentials
            WHERE category = $1 AND is_default_fallback = TRUE AND enabled = TRUE
            LIMIT 1"#,
        q.category
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    if let Some(fb) = fb {
        if !seen.contains(&fb.credential_id) {
            out.push(json!({
                "credential_id":     fb.credential_id,
                "label":             fb.label,
                "provider_name":     fb.provider_name,
                "model":             fb.model,
                "enabled":           fb.enabled,
                "last_health_ok":    fb.last_health_ok,
                "origin":            "default",
                "position":          null,
                "fallback_strategy": "always",
            }));
        }
    }

    Ok((StatusCode::OK, Json(json!({
        "data":          out,
        "category":      q.category,
        "channel_id":    q.channel_id,
        "content_mode":  q.content_mode,
        "pipeline_mode": pm,
    }))))
}

pub(crate) async fn list_marketplace(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let ws_id: i64 = p.wid;

    let catalog = sqlx::query!(
        r#"SELECT id, provider_key, display_name, category, description,
                  logo_url, website_url, mode, capabilities, pricing_notes,
                  cost_unit, regions, has_free_tier, featured, sort_order,
                  config_schema, supported_models, pricing_tier, docs_url,
                  is_platform_seeded
             FROM provider_marketplace_catalog
            ORDER BY category, sort_order, display_name"#
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let cred_counts = sqlx::query!(
        "SELECT provider_name, COUNT(*) AS cnt FROM provider_credentials \
         WHERE workspace_id = $1 GROUP BY provider_name",
        ws_id
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let counts: std::collections::HashMap<String, i64> = cred_counts
        .into_iter()
        .map(|r| (r.provider_name, r.cnt.unwrap_or(0)))
        .collect();

    let data: Vec<Value> = catalog.iter().map(|r| {
        let cnt = counts.get(&r.provider_key).copied().unwrap_or(0);
        json!({
            "id":               r.id,
            "provider_key":     r.provider_key,
            "display_name":     r.display_name,
            "category":         r.category,
            "description":      r.description,
            "logo_url":         r.logo_url,
            "website_url":      r.website_url,
            "mode":             r.mode,
            "capabilities":     r.capabilities,
            "pricing_notes":    r.pricing_notes,
            "cost_unit":        r.cost_unit,
            "regions":          r.regions,
            "has_free_tier":    r.has_free_tier,
            "featured":         r.featured,
            "sort_order":       r.sort_order,
            "config_schema":    r.config_schema,
            "supported_models": r.supported_models,
            "pricing_tier":     r.pricing_tier,
            "docs_url":         r.docs_url,
            "is_platform_seeded": r.is_platform_seeded,
            "credential_count": cnt,
            "connected":        cnt > 0,
        })
    }).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn catalog_for_category(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<CatalogQuery>,
) -> ApiResult<impl IntoResponse> {
    let cat = sqlx::query!("SELECT kind FROM provider_categories WHERE name = $1", q.category)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound(format!("Unknown category {:?}", q.category)))?;

    let rows = sqlx::query!(
        r#"SELECT pmc.provider_key, pmc.display_name, pmc.description, pmc.logo_url,
                  pmc.has_free_tier, pmc.cost_unit, pmc.config_schema, pmc.supported_models,
                  pmc.docs_url, pmc.pricing_tier, pmc.is_user_defined, pmc.is_callable
             FROM provider_marketplace_catalog pmc
             JOIN provider_categories pc ON pc.name = pmc.category
            WHERE pc.kind = $1
            ORDER BY pmc.is_user_defined NULLS FIRST, pmc.sort_order, pmc.display_name"#,
        cat.kind
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "provider_key":     r.provider_key,
        "display_name":     r.display_name,
        "description":      r.description,
        "logo_url":         r.logo_url,
        "has_free_tier":    r.has_free_tier,
        "cost_unit":        r.cost_unit,
        "config_schema":    r.config_schema,
        "supported_models": r.supported_models,
        "docs_url":         r.docs_url,
        "pricing_tier":     r.pricing_tier,
        "is_user_defined":  r.is_user_defined,
        "is_callable":      r.is_callable,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data, "kind": cat.kind }))))
}

pub(crate) async fn setup_checklist(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let cats = sqlx::query!("SELECT name FROM provider_categories ORDER BY name")
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let mut result: Vec<Value> = Vec::new();
    let mut total_ok: i64 = 0;

    for cat in &cats {
        let cname = &cat.name;
        let cred = sqlx::query!(
            r#"SELECT COUNT(*) AS total,
                      SUM(CASE WHEN enabled THEN 1 ELSE 0 END) AS enabled_count,
                      SUM(CASE WHEN last_health_ok THEN 1 ELSE 0 END) AS healthy_count
                 FROM provider_credentials WHERE category = $1"#,
            cname
        )
        .fetch_one(&pool)
        .await
        .map_err(ApiError::Database)?;

        let chain_count = sqlx::query_scalar!(
            "SELECT COUNT(*) FROM provider_chains_v2 WHERE category = $1", cname
        )
        .fetch_one(&pool)
        .await
        .map_err(ApiError::Database)?
        .unwrap_or(0);

        let ok = cred.enabled_count.unwrap_or(0) > 0;
        if ok { total_ok += 1; }

        result.push(json!({
            "category":      cname,
            "credentials":   cred.total.unwrap_or(0),
            "enabled":       cred.enabled_count.unwrap_or(0),
            "healthy":       cred.healthy_count.unwrap_or(0),
            "chain_entries": chain_count,
            "ok":            ok,
        }));
    }

    let total = result.len() as i64;
    Ok((StatusCode::OK, Json(json!({
        "data": result,
        "summary": {
            "total_categories": total,
            "configured":       total_ok,
            "complete":         total_ok == total,
        }
    }))))
}

pub(crate) async fn list_routes(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ScopeQuery>,
) -> ApiResult<impl IntoResponse> {
    let scope = q.scope.as_deref().unwrap_or("workspace");

    let rows = sqlx::query!(
        r#"SELECT r.id, r.scope, r.scope_id, r.category, r.policy,
                  r.custom_rules, r.primary_credential_id, r.fallback_chain,
                  r.enabled, r.updated_at,
                  c.label AS primary_label, c.provider_name AS primary_provider
             FROM provider_routes r
             LEFT JOIN provider_credentials c ON c.id = r.primary_credential_id
            WHERE r.scope = $1 AND ($2::text IS NULL OR r.scope_id = $2)
            ORDER BY r.category"#,
        scope, q.scope_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":                   r.id,
        "scope":                r.scope,
        "scope_id":             r.scope_id,
        "category":             r.category,
        "policy":               r.policy,
        "custom_rules":         r.custom_rules,
        "primary_credential_id": r.primary_credential_id,
        "fallback_chain":       r.fallback_chain,
        "enabled":              r.enabled,
        "updated_at":           r.updated_at.to_rfc3339(),
        "primary_label":        r.primary_label,
        "primary_provider":     r.primary_provider,
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_quotas(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ScopeQuery>,
) -> ApiResult<impl IntoResponse> {
    let scope = q.scope.as_deref().unwrap_or("workspace");

    let rows = sqlx::query!(
        r#"SELECT id, scope, scope_id, category, monthly_cap_usd::float8 AS "monthly_cap_usd: f64", current_spend::float8 AS "current_spend: f64",
                  period_start, alert_pct, hard_limit, updated_at
             FROM provider_quotas
            WHERE scope = $1 AND ($2::text IS NULL OR scope_id = $2)
            ORDER BY category NULLS FIRST"#,
        scope, q.scope_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":               r.id,
        "scope":            r.scope,
        "scope_id":         r.scope_id,
        "category":         r.category,
        "monthly_cap_usd":  r.monthly_cap_usd,
        "current_spend":    r.current_spend,
        "period_start":     r.period_start.to_string(),
        "alert_pct":        r.alert_pct,
        "hard_limit":       r.hard_limit,
        "updated_at":       r.updated_at.to_rfc3339(),
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn list_audit_log(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<AuditLogQuery>,
) -> ApiResult<impl IntoResponse> {
    let lim = q.limit.unwrap_or(100).min(500);

    macro_rules! audit_row_to_json {
        ($r:expr) => { json!({
            "id":          $r.id,
            "actor_label": $r.actor_label,
            "action":      $r.action,
            "target_type": $r.target_type,
            "target_id":   $r.target_id,
            "before":      $r.before,
            "after":       $r.after,
            "created_at":  $r.created_at.to_rfc3339(),
        }) }
    }

    let data: Vec<Value> = if let Some(cred_id) = q.credential_id {
        let cred_str = cred_id.to_string();
        sqlx::query!(
            r#"SELECT a.id, a.actor_label, a.action, a.target_type, a.target_id,
                      a.before, a.after, a.created_at
                 FROM audit_log_v2 a
                WHERE a.action LIKE 'provider.%'
                  AND a.target_type = 'provider_credential'
                  AND a.target_id = $1
                ORDER BY a.created_at DESC LIMIT $2"#,
            cred_str, lim
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter().map(|r| audit_row_to_json!(r)).collect()
    } else if let Some(ref cat) = q.category {
        sqlx::query!(
            r#"SELECT DISTINCT ON (a.id)
                      a.id, a.actor_label, a.action, a.target_type, a.target_id,
                      a.before, a.after, a.created_at
                 FROM audit_log_v2 a
                 JOIN provider_credentials pc ON pc.id::text = a.target_id AND pc.category = $1
                WHERE a.action LIKE 'provider.%'
                ORDER BY a.id DESC, a.created_at DESC LIMIT $2"#,
            cat, lim
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter().map(|r| audit_row_to_json!(r)).collect()
    } else {
        sqlx::query!(
            r#"SELECT a.id, a.actor_label, a.action, a.target_type, a.target_id,
                      a.before, a.after, a.created_at
                 FROM audit_log_v2 a
                WHERE a.action LIKE 'provider.%'
                ORDER BY a.created_at DESC LIMIT $1"#,
            lim
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter().map(|r| audit_row_to_json!(r)).collect()
    };

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn credential_health(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(credential_id): Path<i64>,
    Query(q): Query<HealthQuery>,
) -> ApiResult<impl IntoResponse> {
    let lim = q.limit.unwrap_or(50).min(200);

    let rows = sqlx::query!(
        "SELECT ok, latency_ms, error, checked_at \
         FROM provider_health_log \
         WHERE credential_id = $1 \
         ORDER BY checked_at DESC LIMIT $2",
        credential_id, lim
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "ok":         r.ok,
        "latency_ms": r.latency_ms,
        "error":      r.error,
        "checked_at": r.checked_at.to_rfc3339(),
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

pub(crate) async fn sandbox_runs(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<SandboxRunsQuery>,
) -> ApiResult<impl IntoResponse> {
    let lim = q.limit.unwrap_or(50).min(200);

    let rows = sqlx::query!(
        r#"SELECT id, credential_id, capability, input_payload,
                  output_payload, ok, error, latency_ms, cost_usd::float8 AS "cost_usd: f64", created_at
             FROM provider_sandbox_runs
            WHERE ($1::bigint IS NULL OR credential_id = $1)
            ORDER BY created_at DESC LIMIT $2"#,
        q.credential_id, lim
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":            r.id,
        "credential_id": r.credential_id,
        "capability":    r.capability,
        "input_payload": r.input_payload,
        "output":        r.output_payload,
        "ok":            r.ok,
        "error":         r.error,
        "latency_ms":    r.latency_ms,
        "cost_usd":      r.cost_usd,
        "created_at":    r.created_at.to_rfc3339(),
    })).collect();

    Ok((StatusCode::OK, Json(json!({ "data": data }))))
}

// ─── MUTATION ENDPOINTS ───────────────────────────────────────────────────────

pub(crate) async fn restore_defaults(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    sqlx::query!("SELECT seed_builtin_provider_taxonomy()")
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;
    audit_log(&pool, AuditCtx::new(&p, "provider.taxonomy.restore_defaults", "provider_taxonomy")).await;
    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn delete_kind(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(kind): Path<String>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let row = sqlx::query_scalar!("SELECT kind FROM provider_kinds WHERE kind = $1", kind)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    if row.is_none() {
        return Err(ApiError::NotFound("Section not found".into()));
    }

    let cat_names: Vec<String> = sqlx::query_scalar!(
        "SELECT name FROM provider_categories WHERE kind = $1", kind
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    for cname in &cat_names {
        purge_category_tx(&mut tx, cname).await?;
    }
    sqlx::query!(
        "DELETE FROM provider_marketplace_catalog WHERE provider_key IN \
         (SELECT pmc.provider_key FROM provider_marketplace_catalog pmc \
          LEFT JOIN provider_categories c ON c.name = pmc.category \
          WHERE c.kind = $1 OR pmc.category = $1)",
        kind
    )
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_kinds WHERE kind = $1", kind)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(kind.clone()),
        after: Some(json!({ "categories_removed": cat_names })),
        ..AuditCtx::new(&p, "provider.kind.delete", "provider_kind")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok", "categories_removed": cat_names }))))
}

pub(crate) async fn create_category(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CategoryIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let label = body.label.trim().to_string();
    if label.is_empty() {
        return Err(ApiError::Validation("Category name is required".into()));
    }
    let kind = slugify(&body.kind, 20);
    sqlx::query_scalar!("SELECT kind FROM provider_kinds WHERE kind = $1", kind)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::Validation(format!("Unknown section {:?}. Create the section first.", kind)))?;

    let name_default = format!("{}_{}", kind, label);
    let name_base = body.name.as_deref().unwrap_or(&name_default);
    let name = slugify(name_base, 40);

    let existing = sqlx::query_scalar!("SELECT name FROM provider_categories WHERE name = $1", name)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!("Category {:?} already exists", name)));
    }

    sqlx::query!(
        "INSERT INTO provider_categories (name, label, kind, description, is_user_defined) \
         VALUES ($1, $2, $3, $4, TRUE)",
        name, label, kind, body.description
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(name.clone()),
        after: Some(json!({ "label": label, "kind": kind })),
        ..AuditCtx::new(&p, "provider.category.create", "provider_category")
    }).await;

    Ok((StatusCode::CREATED, Json(json!({ "status": "ok", "name": name, "label": label, "kind": kind }))))
}

pub(crate) async fn rename_category(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(name): Path<String>,
    Json(body): Json<RenameCategoryIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let label = body.label.trim().to_string();
    if label.is_empty() {
        return Err(ApiError::Validation("label is required".into()));
    }

    let existing = sqlx::query_scalar!("SELECT name FROM provider_categories WHERE name = $1", name)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    if existing.is_none() {
        return Err(ApiError::NotFound("Category not found".into()));
    }

    sqlx::query!("UPDATE provider_categories SET label = $1 WHERE name = $2", label, name)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(name.clone()),
        after: Some(json!({ "label": label })),
        ..AuditCtx::new(&p, "provider.category.rename", "provider_category")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok", "name": name, "label": label }))))
}

pub(crate) async fn delete_category(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(name): Path<String>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let existing = sqlx::query_scalar!("SELECT name FROM provider_categories WHERE name = $1", name)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    if existing.is_none() {
        return Err(ApiError::NotFound("Category not found".into()));
    }

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    purge_category_tx(&mut tx, &name).await?;
    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(name.clone()),
        ..AuditCtx::new(&p, "provider.category.delete", "provider_category")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

async fn purge_category_tx(tx: &mut sqlx::Transaction<'_, sqlx::Postgres>, name: &str) -> ApiResult<()> {
    sqlx::query!("DELETE FROM provider_chains_v2 WHERE category = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_priority_chains WHERE category = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_routes WHERE category = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_credentials WHERE category = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_marketplace_catalog WHERE category = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    sqlx::query!("DELETE FROM provider_categories WHERE name = $1", name).execute(&mut **tx).await.map_err(ApiError::Database)?;
    Ok(())
}

pub(crate) async fn set_chain(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(category): Path<String>,
    Json(body): Json<ChainIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let ws_id: i64 = p.wid;

    upsert_chain_inner(
        &pool, "workspace", None, None, "production", &category,
        &body.credential_ids, p.user_id.parse::<i32>().ok(), ws_id,
    ).await?;

    audit_log(&pool, AuditCtx {
        target_id: Some(category.clone()),
        after: Some(json!({ "scope": "workspace", "credential_ids": body.credential_ids })),
        ..AuditCtx::new(&p, "provider.chain.set", "provider_chain")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn upsert_chain_v2(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<ChainV2In>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let ws_id: i64 = p.wid;

    if !body.credential_ids.is_empty() {
        let cat_kind = sqlx::query_scalar!(
            "SELECT kind FROM provider_categories WHERE name = $1", body.category
        )
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

        if let Some(kind) = cat_kind {
            let wrong = sqlx::query!(
                r#"SELECT c.id, pc.kind AS cred_kind
                     FROM provider_credentials c
                     JOIN provider_categories pc ON pc.name = c.category
                    WHERE c.id = ANY($1::bigint[]) AND pc.kind != $2
                    LIMIT 1"#,
                &body.credential_ids, kind
            )
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?;

            if let Some(w) = wrong {
                return Err(ApiError::Validation(format!(
                    "Credential {} is kind {:?} but chain category {:?} expects kind {:?}.",
                    w.id, w.cred_kind, body.category, kind
                )));
            }
        }
    }

    upsert_chain_inner(
        &pool, &body.scope, body.scope_id.as_deref(), body.content_mode.as_deref(),
        &body.pipeline_mode, &body.category, &body.credential_ids,
        p.user_id.parse::<i32>().ok(), ws_id,
    ).await?;

    audit_log(&pool, AuditCtx {
        target_id: Some(format!("{}:{}:{}:{}", body.scope, body.scope_id.as_deref().unwrap_or(""), body.content_mode.as_deref().unwrap_or(""), body.category)),
        after: Some(json!({ "scope": body.scope, "category": body.category, "credential_ids": body.credential_ids })),
        ..AuditCtx::new(&p, "provider.chain_v2.set", "provider_chain_v2")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

async fn upsert_chain_inner(
    pool: &PgPool,
    scope: &str,
    scope_id: Option<&str>,
    content_mode: Option<&str>,
    pipeline_mode: &str,
    category: &str,
    credential_ids: &[i64],
    actor_user_id: Option<i32>,
    workspace_id: i64,
) -> ApiResult<()> {
    let mut tx = pool.begin().await.map_err(ApiError::Database)?;

    sqlx::query!(
        "DELETE FROM provider_chains_v2 \
         WHERE scope = $1 \
           AND ($2::text IS NULL AND scope_id IS NULL OR scope_id = $2) \
           AND ($3::text IS NULL AND content_mode IS NULL OR content_mode = $3) \
           AND COALESCE(pipeline_mode, 'production') = $4 \
           AND category = $5 \
           AND workspace_id = $6",
        scope, scope_id, content_mode, pipeline_mode, category, workspace_id,
    )
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    let mut seen: std::collections::HashSet<i64> = std::collections::HashSet::new();
    let mut position: i16 = 0;
    for &cid in credential_ids {
        if seen.contains(&cid) { continue; }
        seen.insert(cid);
        sqlx::query!(
            "INSERT INTO provider_chains_v2 \
             (scope, scope_id, content_mode, pipeline_mode, category, credential_id, position, workspace_id, created_by) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            scope, scope_id, content_mode, pipeline_mode, category, cid, position, workspace_id, actor_user_id as Option<i32>
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
        position += 1;
    }

    tx.commit().await.map_err(ApiError::Database)?;
    Ok(())
}

pub(crate) async fn delete_chain(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<DeleteChainQuery>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;
    let pm = q.pipeline_mode.as_deref().unwrap_or("production");

    sqlx::query!(
        "DELETE FROM provider_chains_v2 \
         WHERE scope = $1 \
           AND ($2::text IS NULL AND scope_id IS NULL OR scope_id = $2) \
           AND ($3::text IS NULL AND content_mode IS NULL OR content_mode = $3) \
           AND COALESCE(pipeline_mode, 'production') = $4 \
           AND category = $5",
        q.scope, q.scope_id, q.content_mode, pm, q.category,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(format!("{}:{}:{}:{}", q.scope, q.scope_id.as_deref().unwrap_or(""), q.content_mode.as_deref().unwrap_or(""), q.category)),
        ..AuditCtx::new(&p, "provider.chain_v2.delete", "provider_chain_v2")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn reorder_chains(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<ReorderIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    if body.items.is_empty() {
        return Ok((StatusCode::OK, Json(json!({ "status": "ok" }))));
    }

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    for item in &body.items {
        sqlx::query!(
            "UPDATE provider_chains_v2 SET position = $1 WHERE id = $2",
            item.position as i16, item.id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    }
    tx.commit().await.map_err(ApiError::Database)?;

    let ids: Vec<i64> = body.items.iter().map(|i| i.id).collect();
    audit_log(&pool, AuditCtx {
        target_id: Some(ids.iter().map(|i| i.to_string()).collect::<Vec<_>>().join(",")),
        after: Some(json!({ "count": ids.len() })),
        ..AuditCtx::new(&p, "provider.chain.reorder", "provider_chain_v2")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn set_credential_enabled(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(id): Path<i64>,
    Json(body): Json<EnabledIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let rows = sqlx::query!(
        "UPDATE provider_credentials SET enabled = $1 WHERE id = $2",
        body.enabled, id
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if rows.rows_affected() == 0 {
        return Err(ApiError::NotFound("Credential not found".into()));
    }

    audit_log(&pool, AuditCtx {
        target_id: Some(id.to_string()),
        after: Some(json!({ "enabled": body.enabled })),
        ..AuditCtx::new(&p, "provider.credential.enabled_toggle", "provider_credential")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn set_chain_entry_enabled(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(entry_id): Path<i64>,
    Json(body): Json<EnabledIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let rows = sqlx::query!(
        "UPDATE provider_chains_v2 SET is_enabled = $1 WHERE id = $2",
        body.enabled, entry_id
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if rows.rows_affected() == 0 {
        return Err(ApiError::NotFound("Chain entry not found".into()));
    }

    audit_log(&pool, AuditCtx {
        target_id: Some(entry_id.to_string()),
        after: Some(json!({ "enabled": body.enabled })),
        ..AuditCtx::new(&p, "provider.chain_entry.enabled_toggle", "provider_chain_v2")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn set_default_fallback(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(credential_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let cred = sqlx::query!("SELECT category FROM provider_credentials WHERE id = $1", credential_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Credential not found".into()))?;

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;
    sqlx::query!(
        "UPDATE provider_credentials SET is_default_fallback = FALSE WHERE category = $1",
        cred.category
    ).execute(&mut *tx).await.map_err(ApiError::Database)?;
    sqlx::query!(
        "UPDATE provider_credentials SET is_default_fallback = TRUE WHERE id = $1",
        credential_id
    ).execute(&mut *tx).await.map_err(ApiError::Database)?;
    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(credential_id.to_string()),
        after: Some(json!({ "category": cred.category })),
        ..AuditCtx::new(&p, "provider.credential.default_fallback_set", "provider_credential")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn clear_default_fallback(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(credential_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let cred = sqlx::query!("SELECT category FROM provider_credentials WHERE id = $1", credential_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Credential not found".into()))?;

    sqlx::query!(
        "UPDATE provider_credentials SET is_default_fallback = FALSE WHERE id = $1",
        credential_id
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(credential_id.to_string()),
        after: Some(json!({ "category": cred.category })),
        ..AuditCtx::new(&p, "provider.credential.default_fallback_clear", "provider_credential")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn create_marketplace_provider(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<MarketplaceProviderIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let display_name = body.display_name.trim().to_string();
    if display_name.is_empty() {
        return Err(ApiError::Validation("Provider name is required".into()));
    }
    let kind = slugify(&body.kind, 20);
    sqlx::query_scalar!("SELECT kind FROM provider_kinds WHERE kind = $1", kind)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::Validation(format!("Unknown section {:?}. Create the section first.", kind)))?;

    let cat = sqlx::query_scalar!("SELECT name FROM provider_categories WHERE name = $1 LIMIT 1", kind)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;
    let cat_name = if let Some(c) = cat {
        c
    } else {
        sqlx::query_scalar!(
            "SELECT name FROM provider_categories WHERE kind = $1 ORDER BY name LIMIT 1", kind
        )
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::Validation(format!("Section {:?} has no category.", kind)))?
    };

    let pk_base = body.provider_key.as_deref().unwrap_or(&display_name);
    let provider_key = slugify(pk_base, 60);

    let existing = sqlx::query_scalar!(
        "SELECT provider_key FROM provider_marketplace_catalog WHERE provider_key = $1", provider_key
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!("Provider {:?} already exists", provider_key)));
    }

    let config_schema = if body.requires_api_key {
        serde_json::to_value(vec![
            json!({"name":"api_key","type":"password","label":"API Key","required":true}),
            json!({"name":"model","type":"text","label":"Model (optional)","required":false}),
        ]).unwrap()
    } else {
        serde_json::to_value(vec![
            json!({"name":"model","type":"text","label":"Model (optional)","required":false}),
        ]).unwrap()
    };
    let supported_models = serde_json::to_value(&body.supported_models).unwrap();
    let pricing_tier = if body.has_free_tier { "free" } else { "paid" };

    sqlx::query!(
        r#"INSERT INTO provider_marketplace_catalog
              (provider_key, display_name, category, description, mode, capabilities,
               cost_unit, has_free_tier, featured, sort_order,
               config_schema, supported_models, is_platform_seeded, pricing_tier,
               is_user_defined, is_callable)
           VALUES ($1,$2,$3,$4,'byok',ARRAY[]::text[],$5,$6,FALSE,90,
                   $7::jsonb,$8::jsonb,FALSE,$9,TRUE,FALSE)"#,
        provider_key, display_name, cat_name, body.description,
        body.cost_unit, body.has_free_tier,
        config_schema, supported_models, pricing_tier,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(provider_key.clone()),
        after: Some(json!({ "display_name": display_name, "kind": kind })),
        ..AuditCtx::new(&p, "provider.marketplace.create", "provider_marketplace")
    }).await;

    Ok((StatusCode::CREATED, Json(json!({ "status": "ok", "provider_key": provider_key, "category": cat_name }))))
}

pub(crate) async fn delete_marketplace_provider(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(provider_key): Path<String>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let existing = sqlx::query_scalar!(
        "SELECT provider_key FROM provider_marketplace_catalog WHERE provider_key = $1", provider_key
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;
    if existing.is_none() {
        return Err(ApiError::NotFound("Provider not found".into()));
    }

    sqlx::query!("DELETE FROM provider_marketplace_catalog WHERE provider_key = $1", provider_key)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(provider_key.clone()),
        ..AuditCtx::new(&p, "provider.marketplace.delete", "provider_marketplace")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn upsert_route(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(category): Path<String>,
    Json(body): Json<RouteIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let custom_rules = body.custom_rules.clone();
    let fallback_chain = body.fallback_chain.clone();
    let actor_id: i32 = p.user_id.parse().unwrap_or(0);

    let existing = sqlx::query_scalar!(
        "SELECT id FROM provider_routes \
         WHERE scope = $1 AND ($2::text IS NULL AND scope_id IS NULL OR scope_id = $2) AND category = $3",
        body.scope, body.scope_id, category
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let rid: i64 = if let Some(id) = existing {
        sqlx::query!(
            "UPDATE provider_routes SET policy=$1, custom_rules=$2::jsonb, \
             primary_credential_id=$3, fallback_chain=$4::bigint[], updated_at=NOW() WHERE id=$5",
            body.policy, custom_rules, body.primary_credential_id, &fallback_chain, id
        )
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;
        id
    } else {
        sqlx::query_scalar!(
            "INSERT INTO provider_routes \
             (scope, scope_id, category, policy, custom_rules, primary_credential_id, fallback_chain, created_by) \
             VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7::bigint[],$8) RETURNING id",
            body.scope, body.scope_id, category, body.policy,
            custom_rules, body.primary_credential_id, &fallback_chain, actor_id
        )
        .fetch_one(&pool)
        .await
        .map_err(ApiError::Database)?
    };

    audit_log(&pool, AuditCtx {
        target_id: Some(rid.to_string()),
        after: Some(json!({ "category": category, "policy": body.policy })),
        ..AuditCtx::new(&p, "provider.route.upsert", "provider_route")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok", "id": rid }))))
}

pub(crate) async fn create_quota(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<QuotaIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let qid: i64 = sqlx::query_scalar!(
        r#"INSERT INTO provider_quotas (scope, scope_id, category, monthly_cap_usd, alert_pct, hard_limit)
           VALUES ($1,$2,$3,$4::float8,$5,$6)
           ON CONFLICT (scope, scope_id, category)
           DO UPDATE SET monthly_cap_usd=EXCLUDED.monthly_cap_usd,
                         alert_pct=EXCLUDED.alert_pct, hard_limit=EXCLUDED.hard_limit,
                         updated_at=NOW()
           RETURNING id"#,
        body.scope, body.scope_id, body.category,
        body.monthly_cap_usd, body.alert_pct as i16, body.hard_limit,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        target_id: Some(qid.to_string()),
        after: Some(json!({ "scope": body.scope, "monthly_cap_usd": body.monthly_cap_usd })),
        ..AuditCtx::new(&p, "provider.quota.upsert", "provider_quota")
    }).await;

    Ok((StatusCode::CREATED, Json(json!({ "status": "ok", "id": qid }))))
}

pub(crate) async fn update_quota(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(quota_id): Path<i64>,
    Json(body): Json<QuotaIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let res = sqlx::query!(
        "UPDATE provider_quotas SET monthly_cap_usd=$1::float8, alert_pct=$2, hard_limit=$3, updated_at=NOW() WHERE id=$4",
        body.monthly_cap_usd, body.alert_pct as i16, body.hard_limit, quota_id
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Quota not found".into()));
    }

    audit_log(&pool, AuditCtx {
        target_id: Some(quota_id.to_string()),
        after: Some(json!({ "monthly_cap_usd": body.monthly_cap_usd })),
        ..AuditCtx::new(&p, "provider.quota.update", "provider_quota")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}

pub(crate) async fn delete_quota(
    AuthUser(p): AuthUser,
    State(pool): State<PgPool>,
    Path(quota_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&p)?;

    let res = sqlx::query!("DELETE FROM provider_quotas WHERE id = $1", quota_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Quota not found".into()));
    }

    audit_log(&pool, AuditCtx {
        target_id: Some(quota_id.to_string()),
        ..AuditCtx::new(&p, "provider.quota.delete", "provider_quota")
    }).await;

    Ok((StatusCode::OK, Json(json!({ "status": "ok" }))))
}
