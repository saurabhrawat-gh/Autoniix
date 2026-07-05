//! Native Rust handlers for finishing config endpoints
//! (finishing.py — 3 endpoints)
//!
//!   GET /channels/:id/settings/finishing  — read config (upsert-on-read)
//!   PUT /channels/:id/settings/finishing  — partial update + audit
//!   GET /finishing/presets                — static preset list (no auth needed in Python, kept authed here)

use axum::{
    extract::{Path, State},
    http::HeaderMap,
    routing::get,
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

// Preset keys must match channel_finishing_config CHECK constraint
const PRESET_KEYS: &[&str] = &[
    "cinematic", "clean_bright", "warm_gold", "cool_blue",
    "vintage", "documentary", "neon_dark",
];

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/channels/:channel_id/settings/finishing", get(get_finishing_config).put(put_finishing_config))
        .route("/api/v2/finishing/presets", get(list_presets))
        .with_state(pool)
}

// ── body struct ────────────────────────────────────────────────────────────────

#[derive(Deserialize, Default)]
struct FinishingUpdate {
    require_resolve_finish:  Option<bool>,
    color_grade_preset:      Option<String>,
    audio_denoise:           Option<bool>,
    audio_eq:                Option<bool>,
    audio_compress:          Option<bool>,
    audio_music_duck:        Option<bool>,
    audio_loudness_lufs:     Option<f64>,
    audio_true_peak_dbtps:   Option<f64>,
    output_prores_archive:   Option<bool>,
}

// ── helpers ────────────────────────────────────────────────────────────────────

async fn ensure_config(pool: &PgPool, channel_id: &str) -> Result<(), ApiError> {
    sqlx::query!(
        "INSERT INTO channel_finishing_config (channel_id) VALUES ($1) ON CONFLICT (channel_id) DO NOTHING",
        channel_id,
    )
    .execute(pool).await.map_err(ApiError::Database)?;
    Ok(())
}

// ── GET /channels/:id/settings/finishing ──────────────────────────────────────

async fn get_finishing_config(
    AuthUser(_p): AuthUser,
    State(pool):  State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM channels WHERE channel_id = $1", channel_id,
    )
    .fetch_optional(&pool).await.map_err(ApiError::Database)?;
    if exists.is_none() {
        return Err(ApiError::NotFound("Channel not found".into()));
    }
    ensure_config(&pool, &channel_id).await?;

    let r = sqlx::query!(
        r#"SELECT channel_id,
                  require_resolve_finish, color_grade_preset,
                  audio_denoise, audio_eq, audio_compress, audio_music_duck,
                  audio_loudness_lufs::float8   AS "audio_loudness_lufs!: f64",
                  audio_true_peak_dbtps::float8 AS "audio_true_peak_dbtps!: f64",
                  output_prores_archive, updated_at
             FROM channel_finishing_config WHERE channel_id = $1"#,
        channel_id,
    )
    .fetch_one(&pool).await.map_err(ApiError::Database)?;

    Ok(Json(json!({
        "channel_id": r.channel_id,
        "require_resolve_finish": r.require_resolve_finish,
        "color_grade_preset": r.color_grade_preset,
        "audio_denoise": r.audio_denoise,
        "audio_eq": r.audio_eq,
        "audio_compress": r.audio_compress,
        "audio_music_duck": r.audio_music_duck,
        "audio_loudness_lufs": r.audio_loudness_lufs,
        "audio_true_peak_dbtps": r.audio_true_peak_dbtps,
        "output_prores_archive": r.output_prores_archive,
        "updated_at": r.updated_at,
    })))
}

// ── PUT /channels/:id/settings/finishing ──────────────────────────────────────

async fn put_finishing_config(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Path(channel_id): Path<String>,
    Json(body):       Json<FinishingUpdate>,
) -> ApiResult<Json<Value>> {
    let exists = sqlx::query_scalar!(
        "SELECT 1 FROM channels WHERE channel_id = $1", channel_id,
    )
    .fetch_optional(&pool).await.map_err(ApiError::Database)?;
    if exists.is_none() {
        return Err(ApiError::NotFound("Channel not found".into()));
    }
    if let Some(ref p) = body.color_grade_preset {
        if !PRESET_KEYS.contains(&p.as_str()) {
            return Err(ApiError::Validation(format!("color_grade_preset must be one of {PRESET_KEYS:?}")));
        }
    }
    if let Some(v) = body.audio_loudness_lufs {
        if !(-24.0..=-9.0).contains(&v) {
            return Err(ApiError::Validation("audio_loudness_lufs must be between -24 and -9".into()));
        }
    }
    if let Some(v) = body.audio_true_peak_dbtps {
        if !(-6.0..=-0.1).contains(&v) {
            return Err(ApiError::Validation("audio_true_peak_dbtps must be between -6 and -0.1".into()));
        }
    }

    ensure_config(&pool, &channel_id).await?;

    // Use COALESCE so unset fields keep their current DB value
    let r = sqlx::query!(
        r#"UPDATE channel_finishing_config SET
               require_resolve_finish  = COALESCE($2, require_resolve_finish),
               color_grade_preset      = COALESCE($3, color_grade_preset),
               audio_denoise           = COALESCE($4, audio_denoise),
               audio_eq                = COALESCE($5, audio_eq),
               audio_compress          = COALESCE($6, audio_compress),
               audio_music_duck        = COALESCE($7, audio_music_duck),
               audio_loudness_lufs     = COALESCE($8::float8, audio_loudness_lufs::float8),
               audio_true_peak_dbtps   = COALESCE($9::float8, audio_true_peak_dbtps::float8),
               output_prores_archive   = COALESCE($10, output_prores_archive),
               updated_at              = NOW()
           WHERE channel_id = $1
           RETURNING channel_id,
                     require_resolve_finish, color_grade_preset,
                     audio_denoise, audio_eq, audio_compress, audio_music_duck,
                     audio_loudness_lufs::float8   AS "audio_loudness_lufs!: f64",
                     audio_true_peak_dbtps::float8 AS "audio_true_peak_dbtps!: f64",
                     output_prores_archive, updated_at"#,
        channel_id,
        body.require_resolve_finish,
        body.color_grade_preset,
        body.audio_denoise,
        body.audio_eq,
        body.audio_compress,
        body.audio_music_duck,
        body.audio_loudness_lufs,
        body.audio_true_peak_dbtps,
        body.output_prores_archive,
    )
    .fetch_one(&pool).await.map_err(ApiError::Database)?;

    let after = json!({
        "channel_id": r.channel_id,
        "require_resolve_finish": r.require_resolve_finish,
        "color_grade_preset": r.color_grade_preset,
        "audio_denoise": r.audio_denoise, "audio_eq": r.audio_eq,
        "audio_compress": r.audio_compress, "audio_music_duck": r.audio_music_duck,
        "audio_loudness_lufs": r.audio_loudness_lufs,
        "audio_true_peak_dbtps": r.audio_true_peak_dbtps,
        "output_prores_archive": r.output_prores_archive,
        "updated_at": r.updated_at,
    });

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "channel.finishing.update",
        target_type: "channel", target_id: Some(channel_id),
        before: None, after: Some(after.clone()), headers: Some(&headers),
    }).await;
    Ok(Json(after))
}

// ── GET /finishing/presets ────────────────────────────────────────────────────

async fn list_presets(
    AuthUser(_p): AuthUser,
) -> Json<Value> {
    Json(json!({
        "presets": PRESET_KEYS.iter().map(|k| json!({ "key": k })).collect::<Vec<_>>()
    }))
}
