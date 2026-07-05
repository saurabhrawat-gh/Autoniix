//! Native Rust handlers for `/api/v2/review/**` and `/api/v2/channels/*/settings/review`
//! (review.py — 7 endpoints, review_config.py — 2 endpoints)
//!
//! All native DB. Temporal signal on decide is best-effort and intentionally
//! omitted here (matches Python fallback behaviour).
//! POST /thumbnail/regenerate: native — inserts a thumbnail_versions row with
//! source='regen_requested' so the thumbnail worker can pick it up.

use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    routing::{get, post},
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

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // review.py
        .route("/api/v2/review/queue",                          get(review_queue))
        .route("/api/v2/review/:video_id",                      get(get_review))
        .route("/api/v2/review/:video_id/open",                 post(open_review))
        .route("/api/v2/review/:video_id/decide",               post(decide_review))
        .route("/api/v2/review/:video_id/script/edit",          post(edit_script))
        .route("/api/v2/review/:video_id/thumbnail/regenerate", post(regen_thumbnail))
        .route("/api/v2/review/:video_id/comments",             post(add_comment))
        // review_config.py
        .route("/api/v2/channels/:channel_id/settings/review",  get(get_review_config).put(put_review_config))
        .with_state(pool)
}

// ── query/body structs ─────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct QueueQ {
    #[serde(default = "d_pending")]
    state: String,
    channel_id: Option<String>,
    #[serde(default = "d_100")]
    limit: i64,
}
fn d_pending() -> String { "pending".into() }
fn d_100() -> i64 { 100 }

#[derive(Deserialize)]
struct DecisionIn {
    decision: String,
    summary: Option<String>,
}

#[derive(Deserialize)]
struct ScriptEditIn {
    kind: String,
    body: Option<String>,
    prompt: Option<String>,
    range: Option<Value>,
    target_version: Option<i32>,
}

#[derive(Deserialize)]
struct CommentIn {
    artifact: String,
    body: String,
    anchor: Option<Value>,
    parent_id: Option<i64>,
}

#[derive(Deserialize)]
struct ReviewConfigUpdate {
    profile: String,
    gates: Option<Value>,
}

// ── gate constants ─────────────────────────────────────────────────────────────

const GATE_KEYS: &[&str] = &[
    "brand_alignment_report", "final_video", "metadata", "remotion_v3_json",
    "research_data", "scene_images", "script_assets_data", "script_direction_data",
    "script_voice_data", "story_script", "thumbnail", "topic_title", "voice_track",
];

fn gates_for_profile(profile: &str, custom: Option<&Value>) -> Value {
    let on: std::collections::HashSet<&str> = match profile {
        "hands_off"    => std::collections::HashSet::new(),
        "quick"        => ["story_script", "final_video"].iter().copied().collect(),
        "standard"     => ["topic_title", "story_script", "metadata", "thumbnail", "final_video"].iter().copied().collect(),
        "full_control" => GATE_KEYS.iter().copied().collect(),
        "custom"       => {
            if let Some(Value::Object(m)) = custom {
                m.iter().filter(|(_, v)| v.as_bool().unwrap_or(false))
                 .map(|(k, _)| k.as_str())
                 .filter(|k| GATE_KEYS.contains(k))
                 .collect()
            } else { std::collections::HashSet::new() }
        }
        _ => std::collections::HashSet::new(),
    };
    let mut map = serde_json::Map::new();
    for &k in GATE_KEYS {
        map.insert(k.to_string(), Value::Bool(on.contains(k)));
    }
    Value::Object(map)
}

// ── GET /review/queue ──────────────────────────────────────────────────────────

async fn review_queue(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<QueueQ>,
) -> ApiResult<Json<Value>> {
    let lim = q.limit.clamp(1, 500);
    let rows = if let Some(ref ch) = q.channel_id {
        sqlx::query!(
            r#"SELECT rs.id, rs.video_id, rs.channel_id, rs.state,
                      rs.opened_at, rs.expires_at,
                      v.title, v.topic, v.content_mode,
                      v.thumbnail_variants_urls,
                      v.authenticity_score::float8 AS "authenticity_score?: f64"
                 FROM review_sessions rs
                 JOIN videos v ON v.content_id = rs.video_id
                WHERE rs.state = $1 AND rs.channel_id = $2
                ORDER BY rs.opened_at DESC
                LIMIT $3"#,
            q.state, ch, lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| json!({
            "id": r.id, "video_id": r.video_id, "channel_id": r.channel_id,
            "state": r.state, "opened_at": r.opened_at, "expires_at": r.expires_at,
            "title": r.title, "topic": r.topic, "content_mode": r.content_mode,
            "thumbnail_variants_urls": r.thumbnail_variants_urls,
            "authenticity_score": r.authenticity_score
        }))
        .collect::<Vec<_>>()
    } else {
        sqlx::query!(
            r#"SELECT rs.id, rs.video_id, rs.channel_id, rs.state,
                      rs.opened_at, rs.expires_at,
                      v.title, v.topic, v.content_mode,
                      v.thumbnail_variants_urls,
                      v.authenticity_score::float8 AS "authenticity_score?: f64"
                 FROM review_sessions rs
                 JOIN videos v ON v.content_id = rs.video_id
                WHERE rs.state = $1
                ORDER BY rs.opened_at DESC
                LIMIT $2"#,
            q.state, lim,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|r| json!({
            "id": r.id, "video_id": r.video_id, "channel_id": r.channel_id,
            "state": r.state, "opened_at": r.opened_at, "expires_at": r.expires_at,
            "title": r.title, "topic": r.topic, "content_mode": r.content_mode,
            "thumbnail_variants_urls": r.thumbnail_variants_urls,
            "authenticity_score": r.authenticity_score
        }))
        .collect::<Vec<_>>()
    };
    Ok(Json(json!({ "data": rows })))
}

// ── GET /review/:video_id ──────────────────────────────────────────────────────

async fn get_review(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(video_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let video = sqlx::query!(
        "SELECT content_id, title, topic, status, content_mode, review_state,
                thumbnail_variants_urls, channel_id, created_at, updated_at
           FROM videos WHERE content_id = $1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Video not found".into()))?;

    let session = sqlx::query!(
        "SELECT id, state, opened_by, opened_at, decided_by, decided_at, summary, expires_at
           FROM review_sessions WHERE video_id = $1 ORDER BY opened_at DESC LIMIT 1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let scripts = sqlx::query!(
        r#"SELECT id, version, source, content AS "content: Value",
                  diff_summary, created_by, created_at
             FROM script_versions WHERE video_id = $1
             ORDER BY version DESC LIMIT 20"#,
        video_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let thumbs = sqlx::query!(
        r#"SELECT id, version, source, minio_key, prompt,
                  ctr_pred::float8 AS "ctr_pred?: f64",
                  composition AS "composition: Value", created_at
             FROM thumbnail_versions WHERE video_id = $1
             ORDER BY version DESC LIMIT 12"#,
        video_id,
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let comments = if let Some(ref s) = session {
        sqlx::query!(
            r#"SELECT id, artifact, anchor AS "anchor: Value",
                      author_id, body, parent_id, created_at
                 FROM review_comments WHERE session_id = $1
                 ORDER BY created_at"#,
            s.id,
        )
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?
        .into_iter()
        .map(|c| json!({
            "id": c.id, "artifact": c.artifact, "anchor": c.anchor,
            "author_id": c.author_id, "body": c.body,
            "parent_id": c.parent_id, "created_at": c.created_at
        }))
        .collect::<Vec<_>>()
    } else {
        vec![]
    };

    Ok(Json(json!({
        "data": {
            "video": {
                "content_id": video.content_id, "title": video.title,
                "topic": video.topic, "status": video.status,
                "content_mode": video.content_mode, "review_state": video.review_state,
                "thumbnail_variants_urls": video.thumbnail_variants_urls,
                "channel_id": video.channel_id,
                "created_at": video.created_at, "updated_at": video.updated_at
            },
            "session": session.map(|s| json!({
                "id": s.id, "state": s.state, "opened_by": s.opened_by,
                "opened_at": s.opened_at, "decided_by": s.decided_by,
                "decided_at": s.decided_at, "summary": s.summary,
                "expires_at": s.expires_at
            })),
            "script_versions": scripts.iter().map(|s| json!({
                "id": s.id, "version": s.version, "source": s.source,
                "content": s.content, "diff_summary": s.diff_summary,
                "created_by": s.created_by, "created_at": s.created_at
            })).collect::<Vec<_>>(),
            "thumbnail_versions": thumbs.iter().map(|t| json!({
                "id": t.id, "version": t.version, "source": t.source,
                "minio_key": t.minio_key, "prompt": t.prompt,
                "ctr_pred": t.ctr_pred, "composition": t.composition,
                "created_at": t.created_at
            })).collect::<Vec<_>>(),
            "comments": comments
        }
    })))
}

// ── POST /review/:video_id/open ────────────────────────────────────────────────

async fn open_review(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(video_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let channel_id = sqlx::query_scalar!(
        "SELECT channel_id FROM videos WHERE content_id = $1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Video not found".into()))?;

    let opened_by: Option<i32> = actor.user_id.parse().ok();
    let sid = sqlx::query_scalar!(
        r#"INSERT INTO review_sessions (video_id, channel_id, state, opened_by)
           VALUES ($1, $2, 'pending', $3) RETURNING id"#,
        video_id,
        channel_id.unwrap_or_default(),
        opened_by,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query!(
        "UPDATE videos SET review_state = 'pending' WHERE content_id = $1",
        video_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "review.open", target_type: "video",
        target_id: Some(video_id.clone()), before: None, after: None,
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({ "status": "ok", "session_id": sid })))
}

// ── POST /review/:video_id/decide ──────────────────────────────────────────────

async fn decide_review(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(video_id): Path<String>,
    Json(body): Json<DecisionIn>,
) -> ApiResult<Json<Value>> {
    const VALID: &[&str] = &["approved", "needs_edits", "rejected", "regenerating"];
    if !VALID.contains(&body.decision.as_str()) {
        return Err(ApiError::Validation(
            format!("Invalid decision={:?}; expected one of {VALID:?}", body.decision),
        ));
    }

    let session_id = sqlx::query_scalar!(
        "SELECT id FROM review_sessions WHERE video_id = $1 ORDER BY opened_at DESC LIMIT 1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::Conflict("No review session is open".into()))?;

    let decided_by: Option<i32> = actor.user_id.parse().ok();
    sqlx::query!(
        "UPDATE review_sessions SET state=$1, decided_by=$2, decided_at=NOW(), summary=$3 WHERE id=$4",
        body.decision, decided_by, body.summary, session_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query!(
        "UPDATE videos SET review_state=$1, updated_at=NOW() WHERE content_id=$2",
        body.decision, video_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    let audit_action = format!("review.{}", body.decision);
    audit_log(&pool, AuditCtx {
        actor: &actor,
        action: &audit_action,
        target_type: "video",
        target_id: Some(video_id.clone()),
        before: None,
        after: Some(json!({ "summary": body.summary })),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({ "status": "ok" })))
}

// ── POST /review/:video_id/script/edit ────────────────────────────────────────

async fn edit_script(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(video_id): Path<String>,
    Json(body): Json<ScriptEditIn>,
) -> ApiResult<Json<Value>> {
    let final_body = body.body.clone().unwrap_or_default();

    let cur_ver: i32 = sqlx::query_scalar!(
        "SELECT COALESCE(MAX(version), 0) FROM script_versions WHERE video_id = $1",
        video_id,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?
    .unwrap_or(0) as i32;

    let next_v = cur_ver + 1;
    let source = match body.kind.as_str() {
        "full" => "human",
        "section" | "paragraph" | "repetition" => "ai_section",
        "hook" => "ai_full",
        "shorten" => "shorten",
        "expand" => "expand",
        "tone" | "emotion" => "tone_change",
        "restore" => "restore",
        _ => "human",
    };
    let diff = format!("{} edit by {}", body.kind, actor.email);
    let content = json!({
        "raw": final_body, "kind": body.kind,
        "prompt": body.prompt, "range": body.range,
        "ai_used": false
    });
    let created_by: Option<i32> = actor.user_id.parse().ok();

    let vid = sqlx::query_scalar!(
        r#"INSERT INTO script_versions (video_id, version, source, content, diff_summary, created_by)
           VALUES ($1, $2, $3, $4::jsonb, $5, $6) RETURNING id"#,
        video_id,
        next_v as i16,
        source,
        serde_json::to_value(&content).unwrap(),
        diff,
        created_by,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "review.script.edit", target_type: "video",
        target_id: Some(video_id.clone()),
        before: None,
        after: Some(json!({ "version": next_v, "kind": body.kind, "ai_used": false })),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({ "status": "ok", "version": next_v, "version_id": vid, "ai_used": false })))
}

// ── POST /review/:video_id/thumbnail/regenerate ────────────────────────────────
// Native DB: inserts a thumbnail_versions row with source='regen_requested'.
// The thumbnail worker polls for rows with this source and regenerates them.

async fn regen_thumbnail(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Path(video_id):  Path<String>,
) -> ApiResult<Json<Value>> {
    sqlx::query!(
        "SELECT content_id FROM videos WHERE content_id = $1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Video not found".into()))?;

    let next_version: i16 = sqlx::query_scalar!(
        r#"SELECT COALESCE(MAX(version), 0) + 1 AS "v!: i16" FROM thumbnail_versions WHERE video_id = $1"#,
        video_id,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let created_by: Option<i32> = actor.user_id.parse().ok();
    let version_id = sqlx::query_scalar!(
        r#"INSERT INTO thumbnail_versions (video_id, version, source, minio_key, created_by)
           VALUES ($1, $2, 'regen_requested', 'pending', $3)
           RETURNING id"#,
        video_id,
        next_version,
        created_by,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "review.thumbnail.regenerate", target_type: "video",
        target_id: Some(video_id.clone()), before: None,
        after: Some(json!({ "version_id": version_id, "version": next_version })),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({
        "status": "ok",
        "data": {
            "video_id":   video_id,
            "version_id": version_id,
            "version":    next_version,
            "queued":     true,
        }
    })))
}

// ── POST /review/:video_id/comments ───────────────────────────────────────────

async fn add_comment(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    Path(video_id): Path<String>,
    Json(body): Json<CommentIn>,
) -> ApiResult<Json<Value>> {
    let session_id = sqlx::query_scalar!(
        "SELECT id FROM review_sessions WHERE video_id = $1 ORDER BY opened_at DESC LIMIT 1",
        video_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::Conflict("No review session is open".into()))?;

    let author_id: Option<i32> = actor.user_id.parse().ok();
    let anchor = body.anchor.as_ref().map(|v| serde_json::to_value(v).unwrap());

    let cid = sqlx::query_scalar!(
        r#"INSERT INTO review_comments (session_id, artifact, anchor, author_id, body, parent_id)
           VALUES ($1, $2, $3::jsonb, $4, $5, $6) RETURNING id"#,
        session_id,
        body.artifact,
        anchor,
        author_id,
        body.body,
        body.parent_id,
    )
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    sqlx::query!(
        "UPDATE videos SET review_notes_count = review_notes_count + 1 WHERE content_id = $1",
        video_id,
    )
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok(Json(json!({ "status": "ok", "id": cid })))
}

// ── GET /channels/:channel_id/settings/review ─────────────────────────────────

async fn get_review_config(
    AuthUser(_p): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<Json<Value>> {
    let row = sqlx::query!(
        r#"SELECT review_config AS "review_config: Value" FROM channels WHERE channel_id = $1"#,
        channel_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Channel not found".into()))?;

    let cfg = row.review_config;
    let profile = cfg.get("profile").and_then(|v| v.as_str()).unwrap_or("hands_off").to_string();
    let gates = cfg.get("gates").cloned()
        .unwrap_or_else(|| gates_for_profile("hands_off", None));

    Ok(Json(json!({ "channel_id": channel_id, "profile": profile, "gates": gates })))
}

// ── PUT /channels/:channel_id/settings/review ─────────────────────────────────

async fn put_review_config(
    AuthUser(actor): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Path(channel_id): Path<String>,
    Json(body): Json<ReviewConfigUpdate>,
) -> ApiResult<Json<Value>> {
    const PROFILES: &[&str] = &["hands_off", "quick", "standard", "full_control", "custom"];
    if !PROFILES.contains(&body.profile.as_str()) {
        return Err(ApiError::Validation(
            format!("profile must be one of {PROFILES:?}"),
        ));
    }
    if body.profile == "custom" && body.gates.is_none() {
        return Err(ApiError::Validation("gates must be provided when profile is 'custom'".into()));
    }

    let gates = gates_for_profile(&body.profile, body.gates.as_ref());
    let new_cfg = json!({ "profile": body.profile, "gates": gates });

    let updated = sqlx::query!(
        r#"UPDATE channels SET review_config = $1, updated_at = NOW()
            WHERE channel_id = $2 RETURNING channel_id"#,
        new_cfg,
        channel_id,
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    if updated.is_none() {
        return Err(ApiError::NotFound("Channel not found".into()));
    }

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "review_config.updated", target_type: "channel",
        target_id: Some(channel_id.clone()),
        before: None,
        after: Some(new_cfg.clone()),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({ "channel_id": channel_id, "profile": body.profile, "gates": gates })))
}
