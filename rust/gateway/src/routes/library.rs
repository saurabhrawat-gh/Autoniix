//! Native Rust handlers for `/api/v2/library/**`
//! (library.py + library_licenses.py + library_quotas.py — 24 endpoints)
//!
//! All 24 endpoints are now native DB. POST /library/dam/upload generates
//! a presigned S3 PUT URL via S3 V4 signing (no MinIO SDK required).
//! GET /library/music queries asset_library for audio/music rows.

use axum::{
    extract::{Path, Query, State},
    routing::{get, post, put},
    Json, Router,
};
use hmac::{Hmac, Mac};
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row};
use uuid::Uuid;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

type HmacSha256 = Hmac<Sha256>;

fn hmac_sha256(key: &[u8], data: &[u8]) -> Vec<u8> {
    let mut mac = HmacSha256::new_from_slice(key).expect("hmac key length");
    mac.update(data);
    mac.finalize().into_bytes().to_vec()
}

fn s3_presign_put(
    endpoint: &str,
    bucket: &str,
    key: &str,
    access_key: &str,
    secret_key: &str,
    expires: u64,
) -> String {
    let now = chrono::Utc::now();
    let date = now.format("%Y%m%d").to_string();
    let datetime = now.format("%Y%m%dT%H%M%SZ").to_string();
    let region = "us-east-1";
    let host = endpoint
        .trim_start_matches("https://")
        .trim_start_matches("http://");
    let cred_path = format!("{access_key}/{date}/{region}/s3/aws4_request");
    let cred_enc  = cred_path.replace('/', "%2F");
    let qs = format!(
        "X-Amz-Algorithm=AWS4-HMAC-SHA256\
        &X-Amz-Credential={cred_enc}\
        &X-Amz-Date={datetime}\
        &X-Amz-Expires={expires}\
        &X-Amz-SignedHeaders=host"
    );
    let canon = format!("PUT\n/{bucket}/{key}\n{qs}\nhost:{host}\n\nhost\nUNSIGNED-PAYLOAD");
    let canon_hash: String = Sha256::digest(canon.as_bytes())
        .iter().map(|b| format!("{b:02x}")).collect();
    let sts = format!("AWS4-HMAC-SHA256\n{datetime}\n{date}/{region}/s3/aws4_request\n{canon_hash}");
    let k_date    = hmac_sha256(format!("AWS4{secret_key}").as_bytes(), date.as_bytes());
    let k_region  = hmac_sha256(&k_date,    region.as_bytes());
    let k_service = hmac_sha256(&k_region,  b"s3");
    let k_signing = hmac_sha256(&k_service, b"aws4_request");
    let sig: String = hmac_sha256(&k_signing, sts.as_bytes())
        .iter().map(|b| format!("{b:02x}")).collect();
    let scheme = if endpoint.starts_with("https://") { "https" } else { "http" };
    format!("{scheme}://{host}/{bucket}/{key}?{qs}&X-Amz-Signature={sig}")
}

fn slug(name: &str) -> String {
    name.chars()
        .map(|c| if c.is_alphanumeric() || c == '-' { c.to_ascii_lowercase() } else { '-' })
        .collect::<String>()
        .trim_matches('-')
        .to_string()
}

// ── defaults ──────────────────────────────────────────────────────────────────

fn d_60() -> i64 { 60 }
fn d_40() -> i64 { 40 }
fn d_200() -> i64 { 200 }
fn d_30() -> i64 { 30 }
fn d_workspace() -> String { "workspace".into() }
fn d_brand() -> String { "brand".into() }
fn d_manual() -> String { "manual".into() }
fn d_hybrid() -> String { "hybrid".into() }

// ── query-param structs ───────────────────────────────────────────────────────

#[derive(Deserialize)]
struct ListAssetsQ {
    q: Option<String>,
    provider: Option<String>,
    #[serde(default = "d_60")]
    limit: i64,
}

#[derive(Deserialize)]
struct BrandQ {
    channel_id: Option<String>,
}

#[derive(Deserialize)]
struct DamAssetsQ {
    #[serde(default = "d_workspace")]
    scope: String,
    scope_id: Option<String>,
    kind: Option<String>,
    q: Option<String>,
    tag: Option<String>,
    origin: Option<String>,
    #[serde(default = "d_60")]
    limit: i64,
    #[serde(default)]
    offset: i64,
}

#[derive(Deserialize)]
struct PreflightQ {
    sha256: String,
}

#[derive(Deserialize)]
struct ScopeQ {
    #[serde(default = "d_workspace")]
    scope: String,
    scope_id: Option<String>,
}

#[derive(Deserialize)]
struct BrandKitScopeQ {
    #[serde(default = "d_brand")]
    scope: String,
    scope_id: Option<String>,
}

#[derive(Deserialize)]
struct ExpiringQ {
    #[serde(default = "d_30")]
    within_days: i64,
    #[serde(default = "d_workspace")]
    scope: String,
    scope_id: Option<String>,
    #[serde(default = "d_200")]
    limit: i64,
}

#[derive(Deserialize)]
struct QuotasQ {
    scope: Option<String>,
}

#[derive(Deserialize)]
struct CollectionAssetsQ {
    #[serde(default = "d_200")]
    limit: i64,
}

// ── body types ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct AssetPatch {
    display_name: Option<String>,
    tags: Option<Vec<String>>,
    license: Option<String>,
    license_url: Option<String>,
    expires_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Deserialize)]
struct CollectionIn {
    name: String,
    description: Option<String>,
    #[serde(default = "d_manual")]
    kind: String,
    #[serde(default)]
    query: Value,
    #[serde(default)]
    asset_ids: Vec<i64>,
    #[serde(default = "d_workspace")]
    scope: String,
    scope_id: Option<String>,
}

#[derive(Deserialize)]
struct BrandKitIn {
    name: String,
    #[serde(default = "d_brand")]
    scope: String,
    scope_id: Option<String>,
    #[serde(default)]
    logo_asset_ids: Vec<i64>,
    #[serde(default)]
    palette: Value,
    #[serde(default)]
    font_asset_ids: Vec<i64>,
    notes: Option<String>,
}

#[derive(Deserialize)]
struct SearchIn {
    q: Option<String>,
    #[serde(default = "d_workspace")]
    scope: String,
    scope_id: Option<String>,
    kind: Option<String>,
    #[serde(default = "d_40")]
    limit: i64,
    #[serde(default = "d_hybrid")]
    mode: String,
}

// ── router ────────────────────────────────────────────────────────────────────

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/library/assets", get(list_assets))
        .route("/api/v2/library/brand", get(list_brand_assets))
        .route("/api/v2/library/music", get(list_music))
        .route("/api/v2/library/dam/assets/preflight", post(dam_preflight))
        .route("/api/v2/library/dam/assets", get(dam_list_assets))
        .route("/api/v2/library/dam/upload", post(dam_upload))
        .route(
            "/api/v2/library/dam/assets/:asset_id",
            get(dam_get_asset).patch(dam_patch_asset).delete(dam_delete_asset),
        )
        .route("/api/v2/library/dam/tags", get(dam_list_tags))
        .route(
            "/api/v2/library/dam/collections",
            get(dam_list_collections).post(dam_create_collection),
        )
        .route(
            "/api/v2/library/dam/collections/:col_id/assets",
            get(dam_collection_assets),
        )
        .route(
            "/api/v2/library/dam/collections/:col_id",
            put(dam_update_collection).delete(dam_delete_collection),
        )
        .route(
            "/api/v2/library/dam/brand-kits",
            get(dam_list_brand_kits).post(dam_create_brand_kit),
        )
        .route("/api/v2/library/dam/brand-kits/:kit_id", put(dam_update_brand_kit))
        .route("/api/v2/library/dam/search", post(dam_search))
        .route("/api/v2/library/dam/license-catalogue", get(license_catalogue))
        .route("/api/v2/library/dam/licenses/expiring", get(licenses_expiring))
        .route("/api/v2/library/dam/licenses/audit", get(licenses_audit))
        .route("/api/v2/library/dam/quotas/recalculate", post(recalculate_quotas))
        .route("/api/v2/library/dam/quotas", get(list_quotas))
        .with_state(pool)
}

// ── GET /library/music ───────────────────────────────────────────────────────

#[derive(Deserialize)]
struct MusicQ {
    q:     Option<String>,
    #[serde(default = "d_40")]
    limit: i64,
}

async fn list_music(
    AuthUser(_p): AuthUser,
    State(pool):  State<PgPool>,
    Query(q):     Query<MusicQ>,
) -> ApiResult<Json<Value>> {
    let limit = q.limit.clamp(1, 200);
    let mut qb = sqlx::QueryBuilder::new(
        "SELECT id, asset_url, minio_key, provider, \
         duration_s::float8 AS duration_s, quality_score::float8 AS quality_score, \
         license_type, tags, created_at \
         FROM asset_library WHERE asset_type IN ('music','audio')",
    );
    if let Some(ref q_text) = q.q {
        qb.push(" AND (LOWER(COALESCE(tags,'')) LIKE ");
        qb.push_bind(format!("%{}%", q_text.to_lowercase()));
        qb.push(" OR LOWER(COALESCE(query_text,'')) LIKE ");
        qb.push_bind(format!("%{}%", q_text.to_lowercase()));
        qb.push(")");
    }
    qb.push(" ORDER BY quality_score DESC NULLS LAST LIMIT ");
    qb.push_bind(limit);
    let rows: Vec<Value> = qb.build()
        .fetch_all(&pool).await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| json!({
            "id":           r.get::<i64,_>("id"),
            "url":          r.get::<Option<String>,_>("asset_url"),
            "minio_key":    r.get::<Option<String>,_>("minio_key"),
            "provider":     r.get::<Option<String>,_>("provider"),
            "duration_s":   r.get::<Option<f64>,_>("duration_s"),
            "quality_score":r.get::<Option<f64>,_>("quality_score"),
            "license_type": r.get::<Option<String>,_>("license_type"),
            "tags":         r.get::<Option<String>,_>("tags"),
        }))
        .collect();
    let count = rows.len();
    Ok(Json(json!({ "status": "ok", "data": rows, "count": count })))
}

// ── POST /library/dam/upload ─────────────────────────────────────────────────

#[derive(Deserialize)]
struct DamUploadIn {
    display_name: String,
    mime_type:    String,
    #[serde(default)]
    bytes:        i64,
    kind:         Option<String>,
    #[serde(default = "d_workspace")]
    scope:        String,
    scope_id:     Option<String>,
    license:      Option<String>,
    #[serde(default)]
    tags:         Vec<String>,
}

async fn dam_upload(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    Json(body):      Json<DamUploadIn>,
) -> ApiResult<Json<Value>> {
    let ext = body.mime_type.split('/').nth(1).unwrap_or("bin");
    let storage_key = format!("dam/uploads/{}/{}.{}", Uuid::new_v4(), slug(&body.display_name), ext);
    let tags: Vec<String> = body.tags.clone();
    let created_by = actor.user_id.clone();

    let asset_id = sqlx::query_scalar!(
        r#"INSERT INTO dam_assets
               (scope, scope_id, kind, display_name, mime_type, bytes,
                storage_key, origin, license, tags, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, 'upload', $8, $9, $10)
           RETURNING id"#,
        body.scope,
        body.scope_id,
        body.kind,
        body.display_name,
        body.mime_type,
        body.bytes,
        storage_key,
        body.license,
        &tags,
        created_by,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let endpoint = std::env::var("S3_ENDPOINT").unwrap_or_else(|_| "http://minio:9000".into());
    let bucket   = std::env::var("S3_BUCKET").unwrap_or_else(|_|   "autoniix".into());
    let access   = std::env::var("S3_ACCESS_KEY").unwrap_or_default();
    let secret   = std::env::var("S3_SECRET_KEY").unwrap_or_default();
    let upload_url = s3_presign_put(&endpoint, &bucket, &storage_key, &access, &secret, 3600);

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "dam.upload", target_type: "dam_asset",
        target_id: Some(asset_id.to_string()), before: None,
        after: Some(json!({ "storage_key": storage_key, "mime_type": body.mime_type })),
        headers: None,
    }).await;

    Ok(Json(json!({
        "status":      "ok",
        "data": {
            "asset_id":    asset_id,
            "storage_key": storage_key,
            "upload_url":  upload_url,
            "expires_in":  3600,
        }
    })))
}

// ── GET /library/assets ───────────────────────────────────────────────────────

async fn list_assets(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListAssetsQ>,
) -> ApiResult<Json<Value>> {
    let limit = q.limit.clamp(1, 300);
    let rows = sqlx::query!(
        r#"SELECT id,
                  query_text                            AS "query_text?",
                  provider                             AS "provider?",
                  asset_url                            AS "asset_url?",
                  minio_key                            AS "thumbnail_url?",
                  resolution_width                     AS "width?",
                  resolution_height                    AS "height?",
                  duration_s::float8                   AS "duration_seconds?: f64",
                  quality_score::float8                AS "quality_score?: f64",
                  created_at                           AS "created_at?"
             FROM asset_library
            WHERE ($1::text IS NULL
                   OR LOWER(COALESCE(query_text, '')) LIKE '%' || LOWER($1) || '%')
              AND ($2::text IS NULL OR provider = $2)
            ORDER BY quality_score DESC NULLS LAST, created_at DESC
            LIMIT $3"#,
        q.q.as_deref(),
        q.provider.as_deref(),
        limit,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":               r.id,
        "query_text":       r.query_text,
        "provider":         r.provider,
        "asset_url":        r.asset_url,
        "thumbnail_url":    r.thumbnail_url,
        "width":            r.width,
        "height":           r.height,
        "duration_seconds": r.duration_seconds,
        "quality_score":    r.quality_score,
        "created_at":       r.created_at,
    })).collect();
    Ok(Json(json!({ "data": data })))
}

// ── GET /library/brand ────────────────────────────────────────────────────────

async fn list_brand_assets(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<BrandQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT id, channel_id, asset_type, asset_url, metadata, created_at
             FROM brand_assets
            WHERE ($1::text IS NULL OR channel_id = $1)
            ORDER BY created_at DESC
            LIMIT 200"#,
        q.channel_id.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":         r.id,
        "channel_id": r.channel_id,
        "asset_type": r.asset_type,
        "asset_url":  r.asset_url,
        "metadata":   r.metadata,
        "created_at": r.created_at,
    })).collect();
    Ok(Json(json!({ "data": data })))
}

// ── GET /library/dam/assets ───────────────────────────────────────────────────

async fn dam_list_assets(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<DamAssetsQ>,
) -> ApiResult<Json<Value>> {
    let limit = q.limit.clamp(1, 300);
    let offset = q.offset.max(0);
    let rows = sqlx::query!(
        r#"SELECT id, scope, scope_id, kind, display_name, mime_type, bytes,
                  content_hash, storage_key, thumbnail_key, origin, license,
                  expires_at, tags, ai_tags, metadata, created_by, created_at
             FROM dam_assets
            WHERE deleted_at IS NULL
              AND scope = $1
              AND ($2::text IS NULL OR scope_id = $2)
              AND ($3::text IS NULL OR kind = $3)
              AND ($4::text IS NULL OR origin = $4)
              AND ($5::text IS NULL OR $5 = ANY(tags))
              AND ($6::text IS NULL OR
                   to_tsvector('english', display_name) @@
                   plainto_tsquery('english', $6))
            ORDER BY created_at DESC
            LIMIT $7 OFFSET $8"#,
        q.scope,
        q.scope_id.as_deref(),
        q.kind.as_deref(),
        q.origin.as_deref(),
        q.tag.as_deref(),
        q.q.as_deref(),
        limit,
        offset,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":           r.id,
        "scope":        r.scope,
        "scope_id":     r.scope_id,
        "kind":         r.kind,
        "display_name": r.display_name,
        "mime_type":    r.mime_type,
        "bytes":        r.bytes,
        "content_hash": r.content_hash,
        "storage_key":  r.storage_key,
        "thumbnail_key":r.thumbnail_key,
        "origin":       r.origin,
        "license":      r.license,
        "expires_at":   r.expires_at,
        "tags":         r.tags,
        "ai_tags":      r.ai_tags,
        "metadata":     r.metadata,
        "created_by":   r.created_by,
        "created_at":   r.created_at,
    })).collect();
    Ok(Json(json!({ "data": data })))
}

// ── POST /library/dam/assets/preflight ───────────────────────────────────────

async fn dam_preflight(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<PreflightQ>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT id, display_name, storage_key, scope
             FROM dam_assets
            WHERE content_hash = $1 AND deleted_at IS NULL
            LIMIT 1"#,
        q.sha256,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    match row {
        Some(r) => Ok(Json(json!({
            "exists": true,
            "asset": {
                "id":           r.id,
                "display_name": r.display_name,
                "storage_key":  r.storage_key,
                "scope":        r.scope,
            }
        }))),
        None => Ok(Json(json!({ "exists": false }))),
    }
}

// ── GET /library/dam/assets/:asset_id ────────────────────────────────────────

async fn dam_get_asset(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(asset_id): Path<i64>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT id, scope, scope_id, kind, display_name, mime_type, bytes,
                  content_hash, storage_key, thumbnail_key, origin, license,
                  license_url, expires_at, tags, ai_tags, metadata, created_by,
                  created_at, updated_at
             FROM dam_assets
            WHERE id = $1 AND deleted_at IS NULL"#,
        asset_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Asset not found".into()))?;

    let versions = sqlx::query!(
        r#"SELECT id, version_no, bytes, content_hash, note, created_at
             FROM dam_asset_versions
            WHERE asset_id = $1
            ORDER BY version_no DESC"#,
        asset_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let renditions = sqlx::query!(
        r#"SELECT rendition_kind, storage_key, codec, width, height,
                  bitrate_kbps, duration_ms, bytes
             FROM media_renditions
            WHERE asset_id = $1"#,
        asset_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let jobs = sqlx::query!(
        r#"SELECT kind, status, error, finished_at
             FROM media_jobs
            WHERE asset_id = $1
            ORDER BY created_at DESC
            LIMIT 10"#,
        asset_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let asset = json!({
        "id":            row.id,
        "scope":         row.scope,
        "scope_id":      row.scope_id,
        "kind":          row.kind,
        "display_name":  row.display_name,
        "mime_type":     row.mime_type,
        "bytes":         row.bytes,
        "content_hash":  row.content_hash,
        "storage_key":   row.storage_key,
        "thumbnail_key": row.thumbnail_key,
        "origin":        row.origin,
        "license":       row.license,
        "license_url":   row.license_url,
        "expires_at":    row.expires_at,
        "tags":          row.tags,
        "ai_tags":       row.ai_tags,
        "metadata":      row.metadata,
        "created_by":    row.created_by,
        "created_at":    row.created_at,
        "updated_at":    row.updated_at,
        "versions": versions.iter().map(|v| json!({
            "id":           v.id,
            "version_no":   v.version_no,
            "bytes":        v.bytes,
            "content_hash": v.content_hash,
            "note":         v.note,
            "created_at":   v.created_at,
        })).collect::<Vec<_>>(),
        "renditions": renditions.iter().map(|r| json!({
            "rendition_kind": r.rendition_kind,
            "storage_key":    r.storage_key,
            "codec":          r.codec,
            "width":          r.width,
            "height":         r.height,
            "bitrate_kbps":   r.bitrate_kbps,
            "duration_ms":    r.duration_ms,
            "bytes":          r.bytes,
        })).collect::<Vec<_>>(),
        "media_jobs": jobs.iter().map(|j| json!({
            "kind":        j.kind,
            "status":      j.status,
            "error":       j.error,
            "finished_at": j.finished_at,
        })).collect::<Vec<_>>(),
    });
    Ok(Json(json!({ "data": asset })))
}

// ── PATCH /library/dam/assets/:asset_id ──────────────────────────────────────

async fn dam_patch_asset(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(asset_id): Path<i64>,
    Json(body): Json<AssetPatch>,
) -> ApiResult<Json<Value>> {
    if body.display_name.is_none()
        && body.tags.is_none()
        && body.license.is_none()
        && body.license_url.is_none()
        && body.expires_at.is_none()
    {
        return Err(ApiError::Validation("No fields to update".into()));
    }
    sqlx::query!(
        r#"UPDATE dam_assets
              SET display_name = COALESCE($2, display_name),
                  tags         = COALESCE($3::text[], tags),
                  license      = COALESCE($4, license),
                  license_url  = COALESCE($5, license_url),
                  expires_at   = COALESCE($6, expires_at),
                  updated_at   = now()
            WHERE id = $1 AND deleted_at IS NULL"#,
        asset_id,
        body.display_name.as_deref(),
        body.tags.as_ref().map(|v| v.as_slice()) as Option<&[String]>,
        body.license.as_deref(),
        body.license_url.as_deref(),
        body.expires_at,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "ok": true })))
}

// ── DELETE /library/dam/assets/:asset_id ─────────────────────────────────────

async fn dam_delete_asset(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(asset_id): Path<i64>,
) -> ApiResult<Json<Value>> {
    sqlx::query!(
        "UPDATE dam_assets SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL",
        asset_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "ok": true })))
}

// ── GET /library/dam/tags ─────────────────────────────────────────────────────

async fn dam_list_tags(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ScopeQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT DISTINCT unnest(tags) AS "tag!"
             FROM dam_assets
            WHERE scope = $1
              AND deleted_at IS NULL
              AND ($2::text IS NULL OR scope_id = $2)
            ORDER BY 1"#,
        q.scope,
        q.scope_id.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| Value::String(r.tag.clone())).collect();
    Ok(Json(json!({ "data": data })))
}

// ── GET /library/dam/collections ─────────────────────────────────────────────

async fn dam_list_collections(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ScopeQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT id, name, description, kind, query, asset_ids,
                  cover_asset_id, owner_id, created_at
             FROM dam_collections
            WHERE scope = $1
              AND ($2::text IS NULL OR scope_id = $2)
            ORDER BY name"#,
        q.scope,
        q.scope_id.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":             r.id,
        "name":           r.name,
        "description":    r.description,
        "kind":           r.kind,
        "query":          r.query,
        "asset_ids":      r.asset_ids,
        "cover_asset_id": r.cover_asset_id,
        "owner_id":       r.owner_id,
        "created_at":     r.created_at,
    })).collect();
    Ok(Json(json!({ "data": data })))
}

// ── POST /library/dam/collections ────────────────────────────────────────────

async fn dam_create_collection(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<CollectionIn>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"INSERT INTO dam_collections
              (scope, scope_id, name, description, kind, query, asset_ids, owner_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           RETURNING id"#,
        body.scope,
        body.scope_id,
        body.name,
        body.description,
        body.kind,
        body.query as Value,
        body.asset_ids.as_slice() as &[i64],
        principal.user_id,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "id": row.id })))
}

// ── PUT /library/dam/collections/:col_id ─────────────────────────────────────

async fn dam_update_collection(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(col_id): Path<i64>,
    Json(body): Json<CollectionIn>,
) -> ApiResult<Json<Value>> {
    sqlx::query!(
        r#"UPDATE dam_collections
              SET name = $2, description = $3, kind = $4,
                  query = $5, asset_ids = $6, updated_at = now()
            WHERE id = $1"#,
        col_id,
        body.name,
        body.description,
        body.kind,
        body.query as Value,
        body.asset_ids.as_slice() as &[i64],
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "ok": true })))
}

// ── DELETE /library/dam/collections/:col_id ──────────────────────────────────

async fn dam_delete_collection(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(col_id): Path<i64>,
) -> ApiResult<Json<Value>> {
    sqlx::query!("DELETE FROM dam_collections WHERE id = $1", col_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;
    Ok(Json(json!({ "ok": true })))
}

// ── GET /library/dam/collections/:col_id/assets ──────────────────────────────

async fn dam_collection_assets(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(col_id): Path<i64>,
    Query(q): Query<CollectionAssetsQ>,
) -> ApiResult<Json<Value>> {
    let limit = q.limit.clamp(1, 1000);

    let col = sqlx::query!(
        r#"SELECT kind, scope, scope_id, query, asset_ids
             FROM dam_collections WHERE id = $1"#,
        col_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let col = match col {
        Some(c) => c,
        None => return Ok(Json(json!({ "data": [], "count": 0 }))),
    };

    if col.kind == "manual" {
        if col.asset_ids.is_empty() {
            return Ok(Json(json!({ "data": [], "count": 0 })));
        }
        let rows = sqlx::query!(
            r#"SELECT a.id, a.scope, a.scope_id, a.kind, a.display_name, a.mime_type,
                      a.bytes, a.thumbnail_key, a.storage_key, a.origin, a.tags,
                      a.metadata, a.created_at
                 FROM dam_assets a
                WHERE a.id = ANY($1::bigint[]) AND a.deleted_at IS NULL
                ORDER BY array_position($1::bigint[], a.id)"#,
            col.asset_ids.as_slice() as &[i64],
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

        let data: Vec<Value> = rows.iter().map(|r| json!({
            "id":           r.id,
            "scope":        r.scope,
            "scope_id":     r.scope_id,
            "kind":         r.kind,
            "display_name": r.display_name,
            "mime_type":    r.mime_type,
            "bytes":        r.bytes,
            "thumbnail_key":r.thumbnail_key,
            "storage_key":  r.storage_key,
            "origin":       r.origin,
            "tags":         r.tags,
            "metadata":     r.metadata,
            "created_at":   r.created_at,
        })).collect();
        let count = data.len();
        return Ok(Json(json!({ "data": data, "count": count })));
    }

    // Smart collection — apply structural filters from query JSONB
    let q_obj = match &col.query {
        Value::Object(m) => m.clone(),
        _ => Default::default(),
    };

    let mut qb = sqlx::QueryBuilder::<sqlx::Postgres>::new(
        "SELECT a.id, a.scope, a.scope_id, a.kind, a.display_name, a.mime_type, \
         a.bytes, a.thumbnail_key, a.storage_key, a.origin, a.tags, a.metadata, \
         a.created_at FROM dam_assets a WHERE a.deleted_at IS NULL AND a.scope = ",
    );
    qb.push_bind(col.scope.clone());
    if let Some(sid) = &col.scope_id {
        qb.push(" AND a.scope_id = ").push_bind(sid.clone());
    }
    if let Some(Value::Array(kinds)) = q_obj.get("kind") {
        let ks: Vec<String> = kinds.iter().filter_map(|v| v.as_str().map(String::from)).collect();
        if !ks.is_empty() {
            qb.push(" AND a.kind = ANY(").push_bind(ks).push(")");
        }
    }
    if let Some(Value::Array(tags)) = q_obj.get("tags_any") {
        let ts: Vec<String> = tags.iter().filter_map(|v| v.as_str().map(String::from)).collect();
        if !ts.is_empty() {
            qb.push(" AND a.tags && ").push_bind(ts).push("::text[]");
        }
    }
    if let Some(Value::Array(tags)) = q_obj.get("tags_all") {
        let ts: Vec<String> = tags.iter().filter_map(|v| v.as_str().map(String::from)).collect();
        if !ts.is_empty() {
            qb.push(" AND a.tags @> ").push_bind(ts).push("::text[]");
        }
    }
    if let Some(Value::Array(lics)) = q_obj.get("license") {
        let ls: Vec<String> = lics.iter().filter_map(|v| v.as_str().map(String::from)).collect();
        if !ls.is_empty() {
            qb.push(" AND a.license = ANY(").push_bind(ls).push(")");
        }
    }
    qb.push(" ORDER BY a.created_at DESC LIMIT ").push_bind(limit);

    use sqlx::Row as _;
    let rows = qb.build().fetch_all(&pool).await.map_err(ApiError::Database)?;
    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":           r.try_get::<i64, _>("id").unwrap_or(0),
        "scope":        r.try_get::<String, _>("scope").unwrap_or_default(),
        "scope_id":     r.try_get::<Option<String>, _>("scope_id").unwrap_or(None),
        "kind":         r.try_get::<String, _>("kind").unwrap_or_default(),
        "display_name": r.try_get::<String, _>("display_name").unwrap_or_default(),
        "mime_type":    r.try_get::<Option<String>, _>("mime_type").unwrap_or(None),
        "bytes":        r.try_get::<Option<i64>, _>("bytes").unwrap_or(None),
        "thumbnail_key":r.try_get::<Option<String>, _>("thumbnail_key").unwrap_or(None),
        "storage_key":  r.try_get::<Option<String>, _>("storage_key").unwrap_or(None),
        "origin":       r.try_get::<String, _>("origin").unwrap_or_default(),
        "tags":         r.try_get::<Vec<String>, _>("tags").unwrap_or_default(),
        "metadata":     r.try_get::<Value, _>("metadata").unwrap_or(json!({})),
        "created_at":   r.try_get::<chrono::DateTime<chrono::Utc>, _>("created_at").ok(),
    })).collect();
    let count = data.len();
    Ok(Json(json!({ "data": data, "count": count })))
}

// ── GET /library/dam/brand-kits ───────────────────────────────────────────────

async fn dam_list_brand_kits(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<BrandKitScopeQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT id, scope, scope_id, name, version_no, logo_asset_ids, palette,
                  font_asset_ids, lut_asset_id, intro_asset_id, outro_asset_id,
                  notes, created_at
             FROM dam_brand_kits
            WHERE scope = $1
              AND ($2::text IS NULL OR scope_id = $2)
            ORDER BY name"#,
        q.scope,
        q.scope_id.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":             r.id,
        "scope":          r.scope,
        "scope_id":       r.scope_id,
        "name":           r.name,
        "version_no":     r.version_no,
        "logo_asset_ids": r.logo_asset_ids,
        "palette":        r.palette,
        "font_asset_ids": r.font_asset_ids,
        "lut_asset_id":   r.lut_asset_id,
        "intro_asset_id": r.intro_asset_id,
        "outro_asset_id": r.outro_asset_id,
        "notes":          r.notes,
        "created_at":     r.created_at,
    })).collect();
    Ok(Json(json!({ "data": data })))
}

// ── POST /library/dam/brand-kits ──────────────────────────────────────────────

async fn dam_create_brand_kit(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<BrandKitIn>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"INSERT INTO dam_brand_kits
              (scope, scope_id, name, logo_asset_ids, palette, font_asset_ids, notes)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id"#,
        body.scope,
        body.scope_id,
        body.name,
        body.logo_asset_ids.as_slice() as &[i64],
        body.palette as Value,
        body.font_asset_ids.as_slice() as &[i64],
        body.notes,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "id": row.id })))
}

// ── PUT /library/dam/brand-kits/:kit_id ───────────────────────────────────────

async fn dam_update_brand_kit(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(kit_id): Path<i64>,
    Json(body): Json<BrandKitIn>,
) -> ApiResult<Json<Value>> {
    sqlx::query!(
        r#"UPDATE dam_brand_kits
              SET name = $2, logo_asset_ids = $3, palette = $4,
                  font_asset_ids = $5, notes = $6, updated_at = now()
            WHERE id = $1"#,
        kit_id,
        body.name,
        body.logo_asset_ids.as_slice() as &[i64],
        body.palette as Value,
        body.font_asset_ids.as_slice() as &[i64],
        body.notes,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;
    Ok(Json(json!({ "ok": true })))
}

// ── POST /library/dam/search ──────────────────────────────────────────────────

async fn dam_search(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<SearchIn>,
) -> ApiResult<Json<Value>> {
    let limit = body.limit.clamp(1, 300);
    let rows = sqlx::query!(
        r#"SELECT id, scope, scope_id, kind, display_name, mime_type, bytes,
                  thumbnail_key, storage_key, origin, tags, metadata, created_at
             FROM dam_assets
            WHERE deleted_at IS NULL
              AND scope = $1
              AND ($2::text IS NULL OR scope_id = $2)
              AND ($3::text IS NULL OR kind = $3)
              AND ($4::text IS NULL OR
                   (to_tsvector('english', display_name) @@
                    plainto_tsquery('english', $4)
                    OR display_name ILIKE '%' || $4 || '%'))
            ORDER BY created_at DESC
            LIMIT $5"#,
        body.scope,
        body.scope_id.as_deref(),
        body.kind.as_deref(),
        body.q.as_deref(),
        limit,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":           r.id,
        "scope":        r.scope,
        "scope_id":     r.scope_id,
        "kind":         r.kind,
        "display_name": r.display_name,
        "mime_type":    r.mime_type,
        "bytes":        r.bytes,
        "thumbnail_key":r.thumbnail_key,
        "storage_key":  r.storage_key,
        "origin":       r.origin,
        "tags":         r.tags,
        "metadata":     r.metadata,
        "created_at":   r.created_at,
    })).collect();
    let count = data.len();
    let mode = if body.mode.to_lowercase() == "semantic" { "fts_fallback" } else { "fts" };
    Ok(Json(json!({ "data": data, "count": count, "mode": mode })))
}

// ── GET /library/dam/license-catalogue ───────────────────────────────────────

async fn license_catalogue(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<Json<Value>> {
    let fallback = json!([
        {"id":"creative-commons-0",   "label":"CC0 (Public Domain)",    "commercial":true,  "attribution":false},
        {"id":"creative-commons-by",  "label":"CC BY",                  "commercial":true,  "attribution":true},
        {"id":"royalty-free",         "label":"Royalty-Free",           "commercial":true,  "attribution":false},
        {"id":"proprietary-internal", "label":"Proprietary / Internal", "commercial":true,  "attribution":false},
        {"id":"unknown",              "label":"Unknown (Flagged)",      "commercial":false, "attribution":true},
    ]);

    let row = sqlx::query!(
        "SELECT config_value FROM system_config WHERE config_key = $1",
        "library.license_catalogue",
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let (data, source) = match row {
        None => (fallback, "fallback"),
        Some(r) => match serde_json::from_str::<Value>(&r.config_value) {
            Ok(v) => (v, "system_config"),
            Err(_) => (fallback, "fallback"),
        },
    };
    Ok(Json(json!({ "data": data, "source": source })))
}

// ── GET /library/dam/licenses/expiring ───────────────────────────────────────

async fn licenses_expiring(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ExpiringQ>,
) -> ApiResult<Json<Value>> {
    let limit = q.limit.clamp(1, 1000);
    let within_days = q.within_days.clamp(1, 365) as i32;
    let rows = sqlx::query!(
        r#"SELECT id, scope, scope_id, kind, display_name, license, license_url,
                  expires_at, tags, created_at,
                  (expires_at <= NOW())                               AS "expired!",
                  GREATEST(0,
                    EXTRACT(EPOCH FROM (expires_at - NOW())) / 86400.0
                  )::int                                             AS "days_until_expiry!"
             FROM dam_assets
            WHERE deleted_at IS NULL
              AND scope = $1
              AND expires_at IS NOT NULL
              AND expires_at <= NOW() + make_interval(days => $2)
              AND ($3::text IS NULL OR scope_id = $3)
            ORDER BY expires_at ASC
            LIMIT $4"#,
        q.scope,
        within_days,
        q.scope_id.as_deref(),
        limit,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "id":                r.id,
        "scope":             r.scope,
        "scope_id":          r.scope_id,
        "kind":              r.kind,
        "display_name":      r.display_name,
        "license":           r.license,
        "license_url":       r.license_url,
        "expires_at":        r.expires_at,
        "tags":              r.tags,
        "created_at":        r.created_at,
        "expired":           r.expired,
        "days_until_expiry": r.days_until_expiry,
    })).collect();
    let count = data.len();
    Ok(Json(json!({ "data": data, "count": count, "within_days": q.within_days })))
}

// ── GET /library/dam/licenses/audit ──────────────────────────────────────────

async fn licenses_audit(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ScopeQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT COALESCE(NULLIF(license, ''), 'unspecified') AS "license!",
                  COUNT(*)::bigint                             AS "asset_count!",
                  COALESCE(SUM(bytes), 0)::bigint             AS "total_bytes!",
                  COUNT(*) FILTER (
                      WHERE expires_at IS NOT NULL AND expires_at <= NOW()
                  )::bigint                                   AS "expired_count!",
                  COUNT(*) FILTER (
                      WHERE expires_at IS NOT NULL
                        AND expires_at > NOW()
                        AND expires_at <= NOW() + INTERVAL '30 days'
                  )::bigint                                   AS "expiring_30d!"
             FROM dam_assets
            WHERE deleted_at IS NULL
              AND scope = $1
              AND ($2::text IS NULL OR scope_id = $2)
            GROUP BY COALESCE(NULLIF(license, ''), 'unspecified')
            ORDER BY COUNT(*) DESC"#,
        q.scope,
        q.scope_id.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "license":       r.license,
        "asset_count":   r.asset_count,
        "total_bytes":   r.total_bytes,
        "expired_count": r.expired_count,
        "expiring_30d":  r.expiring_30d,
    })).collect();
    let count = data.len();
    Ok(Json(json!({ "data": data, "count": count })))
}

// ── GET /library/dam/quotas ───────────────────────────────────────────────────

async fn list_quotas(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<QuotasQ>,
) -> ApiResult<Json<Value>> {
    let rows = sqlx::query!(
        r#"SELECT scope, scope_id, quota_bytes, used_bytes, calculated_at
             FROM storage_quotas
            WHERE ($1::text IS NULL OR scope = $1)
            ORDER BY scope, scope_id"#,
        q.scope.as_deref(),
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows.iter().map(|r| json!({
        "scope":         r.scope,
        "scope_id":      r.scope_id,
        "quota_bytes":   r.quota_bytes,
        "used_bytes":    r.used_bytes,
        "calculated_at": r.calculated_at,
    })).collect();
    let count = data.len();
    Ok(Json(json!({ "data": data, "count": count })))
}

// ── POST /library/dam/quotas/recalculate ─────────────────────────────────────

async fn recalculate_quotas(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<Json<Value>> {
    if principal.role != "owner"
        && principal.role != "member"
        && principal.global_role != "superadmin"
    {
        return Err(ApiError::ForbiddenWith("owner or member role required".into()));
    }

    let cfg = sqlx::query!(
        "SELECT config_value FROM system_config WHERE config_key = $1",
        "library.default_quotas",
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let defaults: serde_json::Map<String, Value> = cfg
        .and_then(|r| serde_json::from_str(&r.config_value).ok())
        .unwrap_or_default();

    let ws_bytes: i64 = defaults.get("workspace_bytes").and_then(Value::as_i64).unwrap_or(107_374_182_400);
    let brand_bytes: i64 = defaults.get("brand_bytes").and_then(Value::as_i64).unwrap_or(26_843_545_600);
    let chan_bytes: i64 = defaults.get("channel_bytes").and_then(Value::as_i64).unwrap_or(10_737_418_240);
    let proj_bytes: i64 = defaults.get("project_bytes").and_then(Value::as_i64).unwrap_or(5_368_709_120);

    sqlx::query!(
        r#"WITH agg AS (
               SELECT scope,
                      COALESCE(scope_id, '')          AS scope_id,
                      COALESCE(SUM(bytes), 0)::bigint AS used_bytes
                 FROM dam_assets
                WHERE deleted_at IS NULL
                GROUP BY scope, COALESCE(scope_id, '')
           )
           INSERT INTO storage_quotas (scope, scope_id, quota_bytes, used_bytes, calculated_at)
           SELECT scope, scope_id,
                  CASE scope
                      WHEN 'workspace' THEN $1::bigint
                      WHEN 'brand'     THEN $2::bigint
                      WHEN 'channel'   THEN $3::bigint
                      WHEN 'project'   THEN $4::bigint
                      ELSE 0::bigint
                  END,
                  used_bytes, NOW()
             FROM agg
           ON CONFLICT (scope, scope_id) DO UPDATE
               SET used_bytes    = EXCLUDED.used_bytes,
                   calculated_at = NOW()"#,
        ws_bytes,
        brand_bytes,
        chan_bytes,
        proj_bytes,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok(Json(json!({ "status": "ok" })))
}
