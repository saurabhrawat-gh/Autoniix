//! Channel wizard + settings — port of `src/services/dashboard/v2/channels.py`.
//!
//! Pure-DB endpoints are implemented directly in Rust. Temporal-interaction
//! endpoints (trigger, clone, pause, resume, stop) and brand-kit proxy
//! to the legacy Python BFF at the address given by `PYTHON_BFF_URL`
//! (default: `http://localhost:8020`).
//!
//! Known divergence: `POST /ai/field-suggest` returns a heuristic suggestion
//! only. The Python implementation calls the LLM router. This is intentional
//! and logged in the divergence registry.

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use chrono::{DateTime, Utc};
use rand::Rng;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::PgPool;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use crate::{
    audit::{audit_log, AuditCtx},
    auth::password::PasswordManager,
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::Principal,
};

// ── Trigger cooldown guard ────────────────────────────────────────────────────

const TRIGGER_COOLDOWN_SECS: u64 = 600;

static TRIGGER_COOLDOWN: OnceLock<Mutex<HashMap<String, Instant>>> = OnceLock::new();

fn trigger_cooldown_map() -> &'static Mutex<HashMap<String, Instant>> {
    TRIGGER_COOLDOWN.get_or_init(|| Mutex::new(HashMap::new()))
}

// ── Route table ─────────────────────────────────────────────────────────────

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        // Static paths must be registered before /{channel_id} or Axum will
        // try to parse e.g. "presets" as a channel_id path segment.
        .route("/api/v2/channels/presets", get(list_presets))
        .route("/api/v2/channels/stats", get(get_stats))
        .route(
            "/api/v2/channels/drafts",
            get(list_drafts).post(create_draft),
        )
        .route(
            "/api/v2/channels/drafts/:draft_id",
            get(get_draft).put(save_draft),
        )
        .route("/api/v2/channels/ai/field-suggest", post(field_suggest))
        // Config resolution (F2 + F3)
        .route("/api/v2/channels/:channel_id/resolve-config", get(resolve_config))
        .route("/api/v2/workspace/resolve-provider-chain", get(resolve_provider_chain))
        // CRUD
        .route("/api/v2/channels", get(list_channels).post(create_channel))
        .route(
            "/api/v2/channels/:channel_id",
            get(get_channel).put(patch_channel).delete(delete_channel),
        )
        .route("/api/v2/channels/:channel_id/profile", put(upsert_profile))
        .route("/api/v2/channels/:channel_id/export", get(export_channel))
        // Status actions
        .route("/api/v2/channels/:channel_id/enable", put(enable_channel))
        .route("/api/v2/channels/:channel_id/disable", put(disable_channel))
        .route("/api/v2/channels/:channel_id/archive", put(archive_channel))
        .route("/api/v2/channels/:channel_id/restore", put(restore_channel))
        // Sub-resources
        .route(
            "/api/v2/channels/:channel_id/pillars",
            get(list_pillars).post(add_pillar),
        )
        .route(
            "/api/v2/channels/:channel_id/pillars/:pillar_id",
            put(update_pillar).delete(delete_pillar),
        )
        .route(
            "/api/v2/channels/:channel_id/topic-rules",
            get(list_topic_rules).post(add_topic_rule),
        )
        .route(
            "/api/v2/channels/:channel_id/topic-rules/:rule_id",
            delete(delete_topic_rule),
        )
        .route(
            "/api/v2/channels/:channel_id/references",
            get(list_references).post(add_reference),
        )
        .route(
            "/api/v2/channels/:channel_id/references/:ref_id",
            delete(delete_reference),
        )
        .route(
            "/api/v2/channels/:channel_id/memory",
            get(list_memory).post(add_memory),
        )
        // Proxy endpoints (Temporal + brand service)
        .route("/api/v2/channels/:channel_id/trigger", post(proxy_trigger))
        .route("/api/v2/channels/:channel_id/clone", post(proxy_clone))
        .route(
            "/api/v2/channels/:channel_id/brand-kit",
            get(proxy_get_brand_kit).put(proxy_put_brand_kit),
        )
        .route(
            "/api/v2/channels/:channel_id/jobs/:content_id/pause",
            post(proxy_pause_job),
        )
        .route(
            "/api/v2/channels/:channel_id/jobs/:content_id/resume",
            post(proxy_resume_job),
        )
        .route(
            "/api/v2/channels/:channel_id/jobs/:content_id/stop",
            post(proxy_stop_job),
        )
        .with_state(pool)
}

// ── Request / response types ─────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct ChannelCreate {
    channel_id: Option<String>,
    channel_name: String,
    niche: String,
    sub_niche: Option<String>,
    #[serde(default = "default_platform")]
    platform: String,
    handle: Option<String>,
    description: Option<String>,
    #[serde(default = "default_content_mode")]
    content_mode: String,
    #[serde(default = "default_lang")]
    primary_language: String,
    target_audience: Option<String>,
    geography: Option<String>,
    target_age_group: Option<String>,
    tone: Option<String>,
    brand_personality: Option<String>,
    mission: Option<String>,
    vision: Option<String>,
    humor_style: Option<String>,
    narration_style: Option<String>,
    music_style: Option<String>,
    lut_preference: Option<String>,
    transition_preference: Option<String>,
    typography_preference: Option<String>,
    meme_intensity: Option<i32>,
    emotion_intensity: Option<i32>,
    primary_color: Option<String>,
    secondary_color: Option<String>,
    thumbnail_style: Option<String>,
    pacing_style: Option<String>,
    #[serde(default)]
    auto_upload: bool,
    #[serde(default = "default_review")]
    human_review_required: String,
    #[serde(default)]
    human_review_ratio: f64,
    #[serde(default = "default_review_timeout")]
    review_timeout_hours: i32,
    #[serde(default = "default_daily_spend")]
    max_daily_api_spend: f64,
    #[serde(default = "default_short_videos")]
    videos_per_week_short: i32,
    #[serde(default = "default_long_videos")]
    videos_per_week_long: i32,
    #[serde(default = "default_short_duration")]
    short_form_duration: i32,
    #[serde(default = "default_long_duration")]
    long_form_duration: i32,
    elevenlabs_voice_id: Option<String>,
    voice_stability: Option<f64>,
    voice_similarity: Option<f64>,
    voice_style: Option<f64>,
    #[serde(default)]
    pillars: Vec<Value>,
    #[serde(default)]
    topic_rules: Vec<Value>,
    #[serde(default)]
    references: Vec<Value>,
    preset: Option<String>,
    #[serde(default)]
    extra: Value,
    #[serde(default)]
    content_type_tags: Vec<String>,
    publish_cadence: Option<String>,
}

fn default_platform() -> String {
    "youtube".to_string()
}
fn default_content_mode() -> String {
    "short".to_string()
}
fn default_lang() -> String {
    "en".to_string()
}
fn default_review() -> String {
    "first_10".to_string()
}
fn default_review_timeout() -> i32 {
    24
}
fn default_daily_spend() -> f64 {
    5.0
}
fn default_short_videos() -> i32 {
    7
}
fn default_long_videos() -> i32 {
    1
}
fn default_short_duration() -> i32 {
    60
}
fn default_long_duration() -> i32 {
    600
}

#[derive(Debug, Serialize, Deserialize)]
struct ChannelPatch {
    channel_name: Option<String>,
    niche: Option<String>,
    sub_niche: Option<String>,
    status: Option<String>,
    auto_upload: Option<bool>,
    human_review_required: Option<String>,
    human_review_ratio: Option<f64>,
    review_timeout_hours: Option<i32>,
    max_daily_api_spend: Option<f64>,
    handle: Option<String>,
    description: Option<String>,
    primary_language: Option<String>,
    geography: Option<String>,
    target_age_group: Option<String>,
    target_audience: Option<String>,
    tone: Option<String>,
    brand_personality: Option<String>,
    humor_style: Option<String>,
    narration_style: Option<String>,
    music_style: Option<String>,
    lut_preference: Option<String>,
    transition_preference: Option<String>,
    typography_preference: Option<String>,
    meme_intensity: Option<i32>,
    emotion_intensity: Option<i32>,
    primary_color: Option<String>,
    secondary_color: Option<String>,
    thumbnail_style: Option<String>,
    pacing_style: Option<String>,
    elevenlabs_voice_id: Option<String>,
    voice_stability: Option<f64>,
    voice_similarity: Option<f64>,
    voice_style: Option<f64>,
    content_mode: Option<String>,
    content_type_tags: Option<Vec<String>>,
    publish_cadence: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
struct PillarIn {
    name: String,
    description: Option<String>,
    #[serde(default = "default_weight")]
    weight: f64,
    #[serde(default)]
    examples: Vec<String>,
    #[serde(default)]
    position: i32,
}
fn default_weight() -> f64 {
    1.0
}

#[derive(Debug, Deserialize, Serialize)]
struct TopicRuleIn {
    kind: String,
    value: String,
    #[serde(default)]
    metadata: Value,
}

#[derive(Debug, Deserialize, Serialize)]
struct ReferenceIn {
    kind: String,
    label: Option<String>,
    uri: Option<String>,
    minio_key: Option<String>,
    #[serde(default)]
    parsed_metadata: Value,
}

#[derive(Debug, Deserialize, Serialize)]
struct MemoryIn {
    memory_type: String,
    content: Value,
    confidence: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct DraftIn {
    #[serde(default = "default_step")]
    current_step: i32,
    #[serde(default)]
    payload: Value,
}
fn default_step() -> i32 {
    1
}

#[derive(Debug, Deserialize)]
struct FieldSuggestIn {
    field: String,
    #[serde(default)]
    context: Value,
}

#[derive(Debug, Deserialize)]
struct ChannelDeleteIn {
    confirmation: String,
    password: String,
}

#[derive(Debug, Deserialize)]
struct TriggerIn {
    content_mode: Option<String>,
    topic_hint: Option<String>,
    #[serde(default)]
    topic_candidates: Vec<String>,
    max_cost_usd: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct BrandKitBindIn {
    brand_kit_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct ListChannelsQuery {
    #[serde(default)]
    include_archived: bool,
    #[serde(default = "default_enrich")]
    enrich: bool,
}
fn default_enrich() -> bool {
    true
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn require_owner_or_member(p: &Principal) -> ApiResult<()> {
    if p.role == "owner" || p.role == "member" {
        Ok(())
    } else {
        Err(ApiError::ForbiddenWith(
            "owner or member role required".to_string(),
        ))
    }
}

fn require_owner(p: &Principal) -> ApiResult<()> {
    if p.role == "owner" {
        Ok(())
    } else {
        Err(ApiError::ForbiddenWith("owner role required".to_string()))
    }
}

fn new_channel_id(name: &str) -> String {
    let base: String = name
        .to_lowercase()
        .chars()
        .filter(|c| c.is_alphanumeric())
        .take(14)
        .collect();
    let base = if base.is_empty() {
        "ch".to_string()
    } else {
        base
    };
    let suffix = format!("{:04x}", rand::thread_rng().gen::<u16>());
    format!("{base}_{suffix}")
}

fn completeness(profile: &Value) -> i32 {
    let fields = [
        "mission",
        "vision",
        "brand_personality",
        "tone",
        "narration_style",
        "music_style",
        "humor_style",
        "lut_preference",
    ];
    let filled = fields
        .iter()
        .filter(|&&f| {
            profile
                .get(f)
                .and_then(|v| v.as_str())
                .map(|s| !s.is_empty())
                .unwrap_or(false)
        })
        .count();
    ((filled as f64 / fields.len() as f64) * 100.0).round() as i32
}

fn bff_base() -> String {
    std::env::var("PYTHON_BFF_URL").unwrap_or_else(|_| "http://localhost:8020".to_string())
}

// ── List channels ─────────────────────────────────────────────────────────────

async fn list_channels(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ListChannelsQuery>,
) -> ApiResult<impl IntoResponse> {
    let mut sql = r#"
        SELECT c.channel_id, c.channel_name, c.niche, c.sub_niche, c.content_mode,
               c.platform, c.handle, c.status, c.auto_upload,
               c.human_review_required, c.human_review_ratio,
               c.created_at,
               c.primary_language AS language,
               c.publish_cadence,
               c.content_type_tags,
               c.videos_per_week_short,
               c.videos_per_week_long,
               c.environment,
               cp.completeness_score, cp.tone, cp.brand_personality,
               (SELECT COUNT(*) FROM channel_pillars p WHERE p.channel_id = c.channel_id) AS pillar_count,
               (SELECT COUNT(*) FROM channel_references r WHERE r.channel_id = c.channel_id) AS reference_count
          FROM channels c
          LEFT JOIN channel_profiles cp ON cp.channel_id = c.channel_id
         WHERE c.workspace_id = $1
    "#.to_string();

    if !q.include_archived {
        sql.push_str(" AND c.status != 'archived'");
    }
    sql.push_str(" ORDER BY c.created_at DESC, c.channel_id");

    let rows: Vec<sqlx::postgres::PgRow> = sqlx::query(&sql)
        .bind(principal.wid)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    let mut data: Vec<Value> = rows
        .iter()
        .map(|r| {
            use sqlx::Row;
            json!({
                "channel_id": r.try_get::<String, _>("channel_id").ok(),
                "channel_name": r.try_get::<String, _>("channel_name").ok(),
                "niche": r.try_get::<String, _>("niche").ok(),
                "sub_niche": r.try_get::<Option<String>, _>("sub_niche").ok().flatten(),
                "content_mode": r.try_get::<String, _>("content_mode").ok(),
                "platform": r.try_get::<Option<String>, _>("platform").ok().flatten(),
                "handle": r.try_get::<Option<String>, _>("handle").ok().flatten(),
                "status": r.try_get::<String, _>("status").ok(),
                "auto_upload": r.try_get::<bool, _>("auto_upload").ok(),
                "human_review_required": r.try_get::<Option<String>, _>("human_review_required").ok().flatten(),
                "human_review_ratio": r.try_get::<Option<f64>, _>("human_review_ratio").ok().flatten(),
                "created_at": r.try_get::<Option<DateTime<Utc>>, _>("created_at").ok().flatten(),
                "language": r.try_get::<Option<String>, _>("language").ok().flatten(),
                "publish_cadence": r.try_get::<Option<String>, _>("publish_cadence").ok().flatten(),
                "content_type_tags": r.try_get::<Option<Vec<String>>, _>("content_type_tags").ok().flatten().unwrap_or_default(),
                "videos_per_week_short": r.try_get::<Option<i32>, _>("videos_per_week_short").ok().flatten(),
                "videos_per_week_long": r.try_get::<Option<i32>, _>("videos_per_week_long").ok().flatten(),
                "environment": r.try_get::<Option<String>, _>("environment").ok().flatten(),
                "completeness_score": r.try_get::<Option<i32>, _>("completeness_score").ok().flatten(),
                "tone": r.try_get::<Option<String>, _>("tone").ok().flatten(),
                "brand_personality": r.try_get::<Option<String>, _>("brand_personality").ok().flatten(),
                "pillar_count": r.try_get::<i64, _>("pillar_count").ok(),
                "reference_count": r.try_get::<i64, _>("reference_count").ok(),
            })
        })
        .collect();

    if q.enrich && !data.is_empty() {
        enrich_channel_list(&pool, &mut data).await;
    }

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

async fn enrich_channel_list(pool: &PgPool, channels: &mut [Value]) {
    let ids: Vec<String> = channels
        .iter()
        .filter_map(|c| c.get("channel_id")?.as_str().map(String::from))
        .collect();
    if ids.is_empty() {
        return;
    }

    // Stats
    let stat_rows = sqlx::query(
        r#"SELECT channel_id,
                  COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) AS delivered,
                  COUNT(*) FILTER (WHERE status NOT IN
                      ('delivered','test_delivered','failed','stopped','superseded','rejected')) AS in_progress,
                  COUNT(*) AS total
             FROM videos WHERE channel_id = ANY($1)
             GROUP BY channel_id"#,
    )
    .bind(&ids)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut stats_map: HashMap<String, (i64, i64, i64)> = HashMap::new();
    for r in &stat_rows {
        use sqlx::Row;
        let cid: String = r.try_get("channel_id").unwrap_or_default();
        let d: i64 = r.try_get("delivered").unwrap_or(0);
        let ip: i64 = r.try_get("in_progress").unwrap_or(0);
        let t: i64 = r.try_get("total").unwrap_or(0);
        stats_map.insert(cid, (d, ip, t));
    }

    // Weekly usage
    let weekly_rows = sqlx::query(
        r#"SELECT channel_id,
                  COUNT(*) FILTER (WHERE content_mode = 'short'
                      AND status NOT IN ('failed','stopped','superseded','rejected')) AS short_used,
                  COUNT(*) FILTER (WHERE content_mode = 'long_form'
                      AND status NOT IN ('failed','stopped','superseded','rejected')) AS long_used
             FROM videos
            WHERE channel_id = ANY($1)
              AND created_at >= date_trunc('week', NOW())
            GROUP BY channel_id"#,
    )
    .bind(&ids)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut weekly_map: HashMap<String, (i64, i64)> = HashMap::new();
    for r in &weekly_rows {
        use sqlx::Row;
        let cid: String = r.try_get("channel_id").unwrap_or_default();
        let s: i64 = r.try_get("short_used").unwrap_or(0);
        let l: i64 = r.try_get("long_used").unwrap_or(0);
        weekly_map.insert(cid, (s, l));
    }

    // Active jobs
    let job_rows = sqlx::query(
        r#"SELECT DISTINCT ON (channel_id, content_mode)
                  channel_id, content_id, status, content_mode
             FROM videos
            WHERE channel_id = ANY($1)
              AND status NOT IN ('delivered','test_delivered','failed','stopped',
                                 'superseded','rejected','retrying')
            ORDER BY channel_id, content_mode, created_at DESC"#,
    )
    .bind(&ids)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut job_map: HashMap<String, Vec<Value>> = HashMap::new();
    for r in &job_rows {
        use sqlx::Row;
        let cid: String = r.try_get("channel_id").unwrap_or_default();
        let job = json!({
            "content_id": r.try_get::<String, _>("content_id").ok(),
            "status": r.try_get::<String, _>("status").ok(),
            "content_mode": r.try_get::<String, _>("content_mode").ok(),
            "is_paused": false,
        });
        job_map.entry(cid).or_default().push(job);
    }

    for ch in channels.iter_mut() {
        let cid = ch
            .get("channel_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let (d, ip, t) = stats_map.get(&cid).copied().unwrap_or((0, 0, 0));
        let (su, lu) = weekly_map.get(&cid).copied().unwrap_or((0, 0));
        let spw = ch
            .get("videos_per_week_short")
            .and_then(|v| v.as_i64())
            .unwrap_or(7);
        let lpw = ch
            .get("videos_per_week_long")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);

        if let Some(obj) = ch.as_object_mut() {
            obj.insert(
                "stats".to_string(),
                json!({"delivered": d, "in_progress": ip, "total": t}),
            );
            obj.insert(
                "weekly_usage".to_string(),
                json!({
                    "short":    {"used": su, "limit": spw},
                    "long_form": {"used": lu, "limit": lpw},
                }),
            );
            obj.insert(
                "active_jobs".to_string(),
                json!(job_map.get(&cid).cloned().unwrap_or_default()),
            );
        }
    }
}

// ── Presets ───────────────────────────────────────────────────────────────────

async fn list_presets(
    AuthUser(_): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let rows = sqlx::query(
        "SELECT id, name, description, payload, is_system FROM channel_presets ORDER BY is_system DESC, name",
    )
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            use sqlx::Row;
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "name": r.try_get::<String, _>("name").ok(),
                "description": r.try_get::<Option<String>, _>("description").ok().flatten(),
                "payload": r.try_get::<Option<Value>, _>("payload").ok().flatten(),
                "is_system": r.try_get::<bool, _>("is_system").ok(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

// ── Stats ─────────────────────────────────────────────────────────────────────

async fn get_stats(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let ch = sqlx::query(
        r#"SELECT COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'active')   AS active,
                  COUNT(*) FILTER (WHERE status = 'disabled') AS disabled,
                  COUNT(*) FILTER (WHERE status = 'archived') AS archived
             FROM channels WHERE workspace_id = $1"#,
    )
    .bind(principal.wid)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let vid = sqlx::query(
        r#"SELECT COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) AS delivered,
                  COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
                  COUNT(*) FILTER (WHERE status NOT IN
                      ('delivered','test_delivered','failed','stopped','superseded','rejected')) AS in_progress,
                  CAST(COALESCE(SUM(total_cost), 0) AS FLOAT8) AS total_cost
             FROM videos
            WHERE channel_id IN (SELECT channel_id FROM channels WHERE workspace_id=$1)
              AND created_at::date = CURRENT_DATE"#,
    )
    .bind(principal.wid)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    let budget = sqlx::query(
        "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'",
    )
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let stop =
        sqlx::query("SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'")
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?;

    use sqlx::Row;
    let today_cost: f64 = vid.try_get::<f64, _>("total_cost").unwrap_or(0.0);
    let budget_limit: f64 = budget
        .as_ref()
        .and_then(|r| r.try_get::<String, _>("config_value").ok())
        .and_then(|s| s.parse().ok())
        .unwrap_or(0.0);
    let emergency_stop: bool = stop
        .as_ref()
        .and_then(|r| r.try_get::<String, _>("config_value").ok())
        .map(|s| matches!(s.to_lowercase().as_str(), "true" | "1"))
        .unwrap_or(false);

    Ok((
        StatusCode::OK,
        Json(json!({
            "data": {
                "channels": {
                    "total":    ch.try_get::<i64, _>("total").unwrap_or(0),
                    "active":   ch.try_get::<i64, _>("active").unwrap_or(0),
                    "disabled": ch.try_get::<i64, _>("disabled").unwrap_or(0),
                    "archived": ch.try_get::<i64, _>("archived").unwrap_or(0),
                },
                "today": {
                    "videos_total": vid.try_get::<i64, _>("total").unwrap_or(0),
                    "delivered":    vid.try_get::<i64, _>("delivered").unwrap_or(0),
                    "failed":       vid.try_get::<i64, _>("failed").unwrap_or(0),
                    "in_progress":  vid.try_get::<i64, _>("in_progress").unwrap_or(0),
                    "cost":         today_cost,
                },
                "budget": {
                    "daily_limit": budget_limit,
                    "today_cost":  today_cost,
                },
                "emergency_stop": emergency_stop,
            }
        })),
    ))
}

// ── Create channel ────────────────────────────────────────────────────────────

async fn create_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<ChannelCreate>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    if body.platform != "youtube" {
        return Err(ApiError::Validation(
            "Only 'youtube' platform is supported".to_string(),
        ));
    }

    let h = body.handle.as_deref().unwrap_or("").trim();
    if h.is_empty() {
        return Err(ApiError::Validation("handle is required".to_string()));
    }
    if !h.starts_with('@') {
        return Err(ApiError::Validation(
            "handle must start with '@'".to_string(),
        ));
    }

    let channel_id = body
        .channel_id
        .clone()
        .unwrap_or_else(|| new_channel_id(&body.channel_name));

    // Load preset if specified
    let preset_payload: Value = if let Some(ref preset_name) = body.preset {
        sqlx::query("SELECT payload FROM channel_presets WHERE name=$1")
            .bind(preset_name)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?
            .and_then(|r| {
                use sqlx::Row;
                r.try_get::<Option<Value>, _>("payload").ok().flatten()
            })
            .unwrap_or(Value::Null)
    } else {
        Value::Null
    };

    let preset_humor = preset_payload
        .get("humor_style")
        .and_then(|v| v.as_str())
        .map(String::from);
    let preset_narration = preset_payload
        .get("narration_style")
        .and_then(|v| v.as_str())
        .map(String::from);
    let preset_music = preset_payload
        .get("music_style")
        .and_then(|v| v.as_str())
        .map(String::from);
    let preset_pacing = preset_payload
        .get("pacing_style")
        .and_then(|v| v.as_str())
        .map(String::from);

    let mut tx = pool.begin().await.map_err(ApiError::Database)?;

    // Check for duplicate
    let exists: Option<i64> = sqlx::query_scalar("SELECT 1 FROM channels WHERE channel_id=$1")
        .bind(&channel_id)
        .fetch_optional(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    if exists.is_some() {
        return Err(ApiError::Conflict(format!(
            "channel_id {channel_id:?} exists"
        )));
    }

    sqlx::query(
        r#"INSERT INTO channels (
            channel_id, channel_name, niche, sub_niche, content_mode,
            target_audience, primary_language, geography, target_age_group,
            platform, handle, description, mission, vision, brand_personality,
            humor_style, narration_style, music_style, lut_preference,
            transition_preference, typography_preference, meme_intensity,
            emotion_intensity, primary_color, secondary_color, thumbnail_style,
            pacing_style, auto_upload, human_review_required, human_review_ratio,
            review_timeout_hours, max_daily_api_spend,
            videos_per_week_short, videos_per_week_long,
            short_form_duration, long_form_duration,
            elevenlabs_voice_id, voice_stability, voice_similarity, voice_style,
            source, status, environment, workspace_id,
            publish_cadence, content_type_tags
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
            $16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
            $31,$32,$33,$34,$35,$36,$37,$38,$39,$40,$41,$42,$43,$44,
            $45,$46
        )"#,
    )
    .bind(&channel_id)
    .bind(&body.channel_name)
    .bind(&body.niche)
    .bind(&body.sub_niche)
    .bind(&body.content_mode)
    .bind(&body.target_audience)
    .bind(&body.primary_language)
    .bind(&body.geography)
    .bind(&body.target_age_group)
    .bind(&body.platform)
    .bind(&body.handle)
    .bind(&body.description)
    .bind(&body.mission)
    .bind(&body.vision)
    .bind(&body.brand_personality)
    .bind(body.humor_style.as_ref().or(preset_humor.as_ref()))
    .bind(body.narration_style.as_ref().or(preset_narration.as_ref()))
    .bind(body.music_style.as_ref().or(preset_music.as_ref()))
    .bind(&body.lut_preference)
    .bind(&body.transition_preference)
    .bind(&body.typography_preference)
    .bind(body.meme_intensity)
    .bind(body.emotion_intensity)
    .bind(&body.primary_color)
    .bind(&body.secondary_color)
    .bind(&body.thumbnail_style)
    .bind(body.pacing_style.as_ref().or(preset_pacing.as_ref()))
    .bind(body.auto_upload)
    .bind(&body.human_review_required)
    .bind(body.human_review_ratio)
    .bind(body.review_timeout_hours)
    .bind(body.max_daily_api_spend)
    .bind(body.videos_per_week_short)
    .bind(body.videos_per_week_long)
    .bind(body.short_form_duration)
    .bind(body.long_form_duration)
    .bind(&body.elevenlabs_voice_id)
    .bind(body.voice_stability)
    .bind(body.voice_similarity)
    .bind(body.voice_style)
    .bind("wizard")
    .bind("active")
    .bind("production")
    .bind(principal.wid)
    .bind(&body.publish_cadence)
    .bind(&body.content_type_tags)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    // Build profile payload from body fields
    let mut profile_payload = match body.extra {
        Value::Object(ref m) => m.clone(),
        _ => serde_json::Map::new(),
    };
    for (k, v) in [
        (
            "mission",
            body.mission.as_ref().map(|s| Value::String(s.clone())),
        ),
        (
            "vision",
            body.vision.as_ref().map(|s| Value::String(s.clone())),
        ),
        (
            "brand_personality",
            body.brand_personality
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
        ("tone", body.tone.as_ref().map(|s| Value::String(s.clone()))),
        (
            "humor_style",
            body.humor_style.as_ref().map(|s| Value::String(s.clone())),
        ),
        (
            "narration_style",
            body.narration_style
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
        (
            "music_style",
            body.music_style.as_ref().map(|s| Value::String(s.clone())),
        ),
        (
            "lut_preference",
            body.lut_preference
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
        (
            "transition_preference",
            body.transition_preference
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
        (
            "typography_preference",
            body.typography_preference
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
        (
            "primary_language",
            Some(Value::String(body.primary_language.clone())),
        ),
        (
            "geography",
            body.geography.as_ref().map(|s| Value::String(s.clone())),
        ),
        (
            "target_age_group",
            body.target_age_group
                .as_ref()
                .map(|s| Value::String(s.clone())),
        ),
    ] {
        if let Some(val) = v {
            profile_payload.insert(k.to_string(), val);
        }
    }
    if let Some(mi) = body.meme_intensity {
        profile_payload.insert("meme_intensity".to_string(), json!(mi));
    }
    if let Some(ei) = body.emotion_intensity {
        profile_payload.insert("emotion_intensity".to_string(), json!(ei));
    }

    let profile_json = Value::Object(profile_payload.clone());
    let score = completeness(&profile_json);

    sqlx::query(
        r#"INSERT INTO channel_profiles
               (channel_id, payload, mission, vision, brand_personality, tone, completeness_score)
           VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7)"#,
    )
    .bind(&channel_id)
    .bind(&profile_json)
    .bind(&body.mission)
    .bind(&body.vision)
    .bind(&body.brand_personality)
    .bind(&body.tone)
    .bind(score)
    .execute(&mut *tx)
    .await
    .map_err(ApiError::Database)?;

    // Pillars
    for (i, p) in body.pillars.iter().enumerate() {
        sqlx::query(
            r#"INSERT INTO channel_pillars (channel_id, name, description, weight, examples, position)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6)"#,
        )
        .bind(&channel_id)
        .bind(p.get("name").and_then(|v| v.as_str()).unwrap_or(&format!("Pillar {}", i + 1)))
        .bind(p.get("description").and_then(|v| v.as_str()))
        .bind(p.get("weight").and_then(|v| v.as_f64()).unwrap_or(1.0))
        .bind(p.get("examples").cloned().unwrap_or_else(|| json!([])))
        .bind(p.get("position").and_then(|v| v.as_i64()).unwrap_or(i as i64) as i32)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
    }

    // Topic rules
    for r in &body.topic_rules {
        let kind = r.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        let value = r.get("value").and_then(|v| v.as_str()).unwrap_or("");
        if !kind.is_empty() && !value.is_empty() {
            sqlx::query(
                r#"INSERT INTO channel_topic_rules (channel_id, kind, value, metadata)
                   VALUES ($1,$2,$3,$4::jsonb)"#,
            )
            .bind(&channel_id)
            .bind(kind)
            .bind(value)
            .bind(r.get("metadata").cloned().unwrap_or_else(|| json!({})))
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;
        }
    }

    // References
    for r in &body.references {
        let kind = r.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        if !kind.is_empty() {
            sqlx::query(
                r#"INSERT INTO channel_references
                       (channel_id, kind, label, uri, minio_key, parsed_metadata, uploaded_by)
                   VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)"#,
            )
            .bind(&channel_id)
            .bind(kind)
            .bind(r.get("label").and_then(|v| v.as_str()))
            .bind(r.get("uri").and_then(|v| v.as_str()))
            .bind(r.get("minio_key").and_then(|v| v.as_str()))
            .bind(
                r.get("parsed_metadata")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
            )
            .bind(principal.user_id.parse::<i64>().ok())
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;
        }
    }

    tx.commit().await.map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id.clone()),
            after: Some(json!({"channel_name": &body.channel_name, "niche": &body.niche})),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.create", "channel")
        },
    )
    .await;

    Ok((
        StatusCode::OK,
        Json(json!({"status": "ok", "channel_id": channel_id})),
    ))
}

// ── Get channel ───────────────────────────────────────────────────────────────

async fn get_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    let ch = sqlx::query("SELECT * FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;

    let profile = sqlx::query("SELECT * FROM channel_profiles WHERE channel_id=$1")
        .bind(&channel_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

    let pillars =
        sqlx::query("SELECT * FROM channel_pillars WHERE channel_id=$1 ORDER BY position")
            .bind(&channel_id)
            .fetch_all(&pool)
            .await
            .map_err(ApiError::Database)?;

    let rules =
        sqlx::query("SELECT * FROM channel_topic_rules WHERE channel_id=$1 ORDER BY kind, id")
            .bind(&channel_id)
            .fetch_all(&pool)
            .await
            .map_err(ApiError::Database)?;

    let refs = sqlx::query(
        r#"SELECT id, kind, label, uri, minio_key, parsed_metadata, uploaded_at
             FROM channel_references WHERE channel_id=$1 ORDER BY uploaded_at DESC"#,
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    let memory = sqlx::query(
        r#"SELECT id, memory_type, content, confidence, created_at
             FROM channel_memory WHERE channel_id=$1 ORDER BY created_at DESC LIMIT 50"#,
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    fn row_to_value(r: &sqlx::postgres::PgRow) -> Value {
        use sqlx::{Column, Row};
        let cols = r.columns();
        let mut map = serde_json::Map::new();
        for col in cols {
            let name = col.name();
            let val: Value = r
                .try_get::<Option<Value>, _>(name)
                .ok()
                .flatten()
                .or_else(|| {
                    r.try_get::<Option<String>, _>(name)
                        .ok()
                        .flatten()
                        .map(Value::String)
                })
                .or_else(|| {
                    r.try_get::<Option<i64>, _>(name)
                        .ok()
                        .flatten()
                        .map(|n| json!(n))
                })
                .or_else(|| {
                    r.try_get::<Option<bool>, _>(name)
                        .ok()
                        .flatten()
                        .map(Value::Bool)
                })
                .or_else(|| {
                    r.try_get::<Option<f64>, _>(name)
                        .ok()
                        .flatten()
                        .map(|f| json!(f))
                })
                .or_else(|| {
                    r.try_get::<Option<Vec<String>>, _>(name)
                        .ok()
                        .flatten()
                        .map(|v| json!(v))
                })
                .or_else(|| {
                    r.try_get::<Option<DateTime<Utc>>, _>(name)
                        .ok()
                        .flatten()
                        .map(|t| json!(t))
                })
                .unwrap_or(Value::Null);
            map.insert(name.to_string(), val);
        }
        Value::Object(map)
    }

    Ok((
        StatusCode::OK,
        Json(json!({
            "data": {
                "channel": row_to_value(&ch),
                "profile": profile.as_ref().map(row_to_value),
                "pillars": pillars.iter().map(row_to_value).collect::<Vec<_>>(),
                "topic_rules": rules.iter().map(row_to_value).collect::<Vec<_>>(),
                "references": refs.iter().map(row_to_value).collect::<Vec<_>>(),
                "memory": memory.iter().map(row_to_value).collect::<Vec<_>>(),
            }
        })),
    ))
}

// ── Patch channel ─────────────────────────────────────────────────────────────

async fn patch_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<ChannelPatch>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    // Build a dynamic UPDATE from only non-null fields
    let update_body = serde_json::to_value(&body).unwrap_or(Value::Null);
    let has_updates = update_body
        .as_object()
        .map(|m| m.values().any(|v| !v.is_null()))
        .unwrap_or(false);

    if !has_updates {
        return Ok((StatusCode::OK, Json(json!({"status": "noop"}))));
    }

    // Fetch before state for audit log + 404 guard
    let before_row = sqlx::query(
        "SELECT channel_name, niche, sub_niche, status, auto_upload, human_review_required, \
                handle, description, tone, brand_personality FROM channels \
         WHERE channel_id=$1 AND workspace_id=$2",
    )
    .bind(&channel_id)
    .bind(principal.wid)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let before_row =
        before_row.ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;

    let before_snapshot = {
        use sqlx::Row;
        json!({
            "channel_name": before_row.try_get::<Option<String>, _>("channel_name").ok().flatten(),
            "niche": before_row.try_get::<Option<String>, _>("niche").ok().flatten(),
            "sub_niche": before_row.try_get::<Option<String>, _>("sub_niche").ok().flatten(),
            "status": before_row.try_get::<Option<String>, _>("status").ok().flatten(),
            "auto_upload": before_row.try_get::<Option<bool>, _>("auto_upload").ok().flatten(),
            "human_review_required": before_row.try_get::<Option<String>, _>("human_review_required").ok().flatten(),
            "handle": before_row.try_get::<Option<String>, _>("handle").ok().flatten(),
            "description": before_row.try_get::<Option<String>, _>("description").ok().flatten(),
            "tone": before_row.try_get::<Option<String>, _>("tone").ok().flatten(),
            "brand_personality": before_row.try_get::<Option<String>, _>("brand_personality").ok().flatten(),
        })
    };

    // Build query with COALESCE-based selective update for all patchable columns
    sqlx::query(
        r#"UPDATE channels SET
            channel_name         = COALESCE($2, channel_name),
            niche                = COALESCE($3, niche),
            sub_niche            = COALESCE($4, sub_niche),
            status               = COALESCE($5, status),
            auto_upload          = COALESCE($6, auto_upload),
            human_review_required= COALESCE($7, human_review_required),
            human_review_ratio   = COALESCE($8, human_review_ratio),
            review_timeout_hours = COALESCE($9, review_timeout_hours),
            max_daily_api_spend  = COALESCE($10, max_daily_api_spend),
            handle               = COALESCE($11, handle),
            description          = COALESCE($12, description),
            primary_language     = COALESCE($13, primary_language),
            geography            = COALESCE($14, geography),
            target_age_group     = COALESCE($15, target_age_group),
            target_audience      = COALESCE($16, target_audience),
            tone                 = COALESCE($17, tone),
            brand_personality    = COALESCE($18, brand_personality),
            humor_style          = COALESCE($19, humor_style),
            narration_style      = COALESCE($20, narration_style),
            music_style          = COALESCE($21, music_style),
            lut_preference       = COALESCE($22, lut_preference),
            transition_preference= COALESCE($23, transition_preference),
            typography_preference= COALESCE($24, typography_preference),
            meme_intensity       = COALESCE($25, meme_intensity),
            emotion_intensity    = COALESCE($26, emotion_intensity),
            primary_color        = COALESCE($27, primary_color),
            secondary_color      = COALESCE($28, secondary_color),
            thumbnail_style      = COALESCE($29, thumbnail_style),
            pacing_style         = COALESCE($30, pacing_style),
            elevenlabs_voice_id  = COALESCE($31, elevenlabs_voice_id),
            voice_stability      = COALESCE($32, voice_stability),
            voice_similarity     = COALESCE($33, voice_similarity),
            voice_style          = COALESCE($34, voice_style),
            publish_cadence      = COALESCE($35, publish_cadence),
            content_type_tags    = COALESCE($36, content_type_tags),
            content_mode         = COALESCE($37, content_mode),
            updated_at           = NOW()
           WHERE channel_id = $1"#,
    )
    .bind(&channel_id)
    .bind(&body.channel_name)
    .bind(&body.niche)
    .bind(&body.sub_niche)
    .bind(&body.status)
    .bind(body.auto_upload)
    .bind(&body.human_review_required)
    .bind(body.human_review_ratio)
    .bind(body.review_timeout_hours)
    .bind(body.max_daily_api_spend)
    .bind(&body.handle)
    .bind(&body.description)
    .bind(&body.primary_language)
    .bind(&body.geography)
    .bind(&body.target_age_group)
    .bind(&body.target_audience)
    .bind(&body.tone)
    .bind(&body.brand_personality)
    .bind(&body.humor_style)
    .bind(&body.narration_style)
    .bind(&body.music_style)
    .bind(&body.lut_preference)
    .bind(&body.transition_preference)
    .bind(&body.typography_preference)
    .bind(body.meme_intensity)
    .bind(body.emotion_intensity)
    .bind(&body.primary_color)
    .bind(&body.secondary_color)
    .bind(&body.thumbnail_style)
    .bind(&body.pacing_style)
    .bind(&body.elevenlabs_voice_id)
    .bind(body.voice_stability)
    .bind(body.voice_similarity)
    .bind(body.voice_style)
    .bind(&body.publish_cadence)
    .bind(body.content_type_tags.as_deref())
    .bind(&body.content_mode)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id.clone()),
            before: Some(before_snapshot),
            after: Some(update_body),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.patch", "channel")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

// ── Upsert profile ────────────────────────────────────────────────────────────

async fn upsert_profile(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let payload = body.get("payload").cloned().unwrap_or(Value::Null);
    let score = completeness(&payload);

    sqlx::query(
        r#"INSERT INTO channel_profiles
               (channel_id, payload, mission, vision, brand_personality, tone, completeness_score, updated_at)
           VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7, NOW())
           ON CONFLICT (channel_id) DO UPDATE SET
               payload            = EXCLUDED.payload,
               mission            = EXCLUDED.mission,
               vision             = EXCLUDED.vision,
               brand_personality  = EXCLUDED.brand_personality,
               tone               = EXCLUDED.tone,
               completeness_score = EXCLUDED.completeness_score,
               updated_at         = NOW()"#,
    )
    .bind(&channel_id)
    .bind(&payload)
    .bind(payload.get("mission").and_then(|v| v.as_str()))
    .bind(payload.get("vision").and_then(|v| v.as_str()))
    .bind(payload.get("brand_personality").and_then(|v| v.as_str()))
    .bind(payload.get("tone").and_then(|v| v.as_str()))
    .bind(score)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id.clone()),
            after: Some(json!({"completeness": score})),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.profile.upsert", "channel_profile")
        },
    )
    .await;

    Ok((
        StatusCode::OK,
        Json(json!({"status": "ok", "completeness_score": score})),
    ))
}

// ── Status actions ────────────────────────────────────────────────────────────

async fn set_channel_status(
    pool: &PgPool,
    principal: &Principal,
    channel_id: &str,
    new_status: &str,
    action: &str,
    headers: &HeaderMap,
    where_extra: Option<&str>,
) -> ApiResult<impl IntoResponse> {
    let sql = if let Some(extra) = where_extra {
        format!("UPDATE channels SET status='{new_status}', updated_at=NOW() WHERE channel_id=$1 AND {extra}")
    } else {
        format!("UPDATE channels SET status='{new_status}', updated_at=NOW() WHERE channel_id=$1")
    };

    let res = sqlx::query(&sql)
        .bind(channel_id)
        .execute(pool)
        .await
        .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Channel not found".to_string()));
    }

    audit_log(
        pool,
        AuditCtx {
            target_id: Some(channel_id.to_string()),
            headers: Some(headers),
            ..AuditCtx::new(principal, action, "channel")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

async fn enable_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    set_channel_status(
        &pool,
        &principal,
        &channel_id,
        "active",
        "channel.enable",
        &headers,
        None,
    )
    .await
}

async fn disable_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    set_channel_status(
        &pool,
        &principal,
        &channel_id,
        "disabled",
        "channel.disable",
        &headers,
        None,
    )
    .await
}

async fn archive_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    set_channel_status(
        &pool,
        &principal,
        &channel_id,
        "archived",
        "channel.archive",
        &headers,
        None,
    )
    .await
}

async fn restore_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    set_channel_status(
        &pool,
        &principal,
        &channel_id,
        "disabled",
        "channel.restore",
        &headers,
        Some("status='archived'"),
    )
    .await
}

// ── Hard delete ───────────────────────────────────────────────────────────────

async fn delete_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<ChannelDeleteIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner(&principal)?;

    if body.confirmation != "delete" {
        return Err(ApiError::Validation(
            "confirmation must be 'delete'".to_string(),
        ));
    }

    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::ForbiddenWith("No user context".to_string()))?;

    // Re-verify password
    let user = sqlx::query("SELECT password_hash FROM users WHERE id=$1")
        .bind(user_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("User not found".to_string()))?;

    use sqlx::Row;
    let hash: String = user.try_get("password_hash").unwrap_or_default();
    let verified = PasswordManager::verify_password(&body.password, &hash).unwrap_or(false);
    if !verified {
        return Err(ApiError::ForbiddenWith("wrong_password".to_string()));
    }

    // Workspace isolation
    let channel = sqlx::query(
        r#"SELECT channel_id, channel_name, niche, platform, status, workspace_id, created_at
             FROM channels WHERE channel_id=$1"#,
    )
    .bind(&channel_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("channel_not_found".to_string()))?;

    let ws_id: i64 = channel.try_get("workspace_id").unwrap_or(0);
    if ws_id != principal.wid {
        return Err(ApiError::NotFound("channel_not_found".to_string()));
    }

    // Block if videos exist
    let video_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM videos WHERE channel_id=$1")
        .bind(&channel_id)
        .fetch_one(&pool)
        .await
        .map_err(ApiError::Database)?;
    if video_count > 0 {
        return Err(ApiError::Conflict(format!(
            "Cannot delete channel with {video_count} published videos. Archive instead."
        )));
    }

    // Check YouTube linkage
    let yt_linked: Option<i64> = sqlx::query_scalar(
        "SELECT 1 FROM provider_credentials WHERE channel_id=$1 AND category='youtube' LIMIT 1",
    )
    .bind(&channel_id)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    let snapshot = json!({
        "channel_id": channel.try_get::<String, _>("channel_id").ok(),
        "channel_name": channel.try_get::<String, _>("channel_name").ok(),
        "niche": channel.try_get::<String, _>("niche").ok(),
        "platform": channel.try_get::<Option<String>, _>("platform").ok().flatten(),
        "status": channel.try_get::<String, _>("status").ok(),
        "workspace_id": ws_id,
    });

    sqlx::query("DELETE FROM channels WHERE channel_id=$1")
        .bind(&channel_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id.clone()),
            before: Some(snapshot),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.delete", "channel")
        },
    )
    .await;

    if yt_linked.is_some() {
        audit_log(
            &pool,
            AuditCtx {
                target_id: Some(channel_id.clone()),
                before: Some(json!({"channel_id": &channel_id, "reason": "channel_hard_delete"})),
                headers: Some(&headers),
                ..AuditCtx::new(
                    &principal,
                    "provider.youtube.unlink",
                    "provider_credentials",
                )
            },
        )
        .await;
    }

    Ok((
        StatusCode::OK,
        Json(json!({"status": "ok", "data": {"deleted": true, "channel_id": channel_id}})),
    ))
}

// ── Pillars ───────────────────────────────────────────────────────────────────

async fn add_pillar(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<PillarIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let pid: i64 = sqlx::query_scalar(
        r#"INSERT INTO channel_pillars (channel_id, name, description, weight, examples, position)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6) RETURNING id"#,
    )
    .bind(&channel_id)
    .bind(&body.name)
    .bind(&body.description)
    .bind(body.weight)
    .bind(json!(body.examples))
    .bind(body.position)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(pid.to_string()),
            after: Some(serde_json::to_value(&body).unwrap_or(Value::Null)),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.pillar.create", "channel_pillar")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok", "id": pid}))))
}

async fn update_pillar(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, pillar_id)): Path<(String, i64)>,
    headers: HeaderMap,
    Json(body): Json<PillarIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query(
        r#"UPDATE channel_pillars
              SET name=$1, description=$2, weight=$3, examples=$4::jsonb, position=$5
            WHERE id=$6 AND channel_id=$7"#,
    )
    .bind(&body.name)
    .bind(&body.description)
    .bind(body.weight)
    .bind(json!(body.examples))
    .bind(body.position)
    .bind(pillar_id)
    .bind(&channel_id)
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Pillar not found".to_string()));
    }

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(pillar_id.to_string()),
            after: Some(serde_json::to_value(&body).unwrap_or(Value::Null)),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.pillar.update", "channel_pillar")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

async fn delete_pillar(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, pillar_id)): Path<(String, i64)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query("DELETE FROM channel_pillars WHERE id=$1 AND channel_id=$2")
        .bind(pillar_id)
        .bind(&channel_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Pillar not found".to_string()));
    }

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(pillar_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.pillar.delete", "channel_pillar")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

// ── Topic rules ───────────────────────────────────────────────────────────────

async fn add_topic_rule(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<TopicRuleIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let rid: i64 = sqlx::query_scalar(
        r#"INSERT INTO channel_topic_rules (channel_id, kind, value, metadata)
           VALUES ($1,$2,$3,$4::jsonb) RETURNING id"#,
    )
    .bind(&channel_id)
    .bind(&body.kind)
    .bind(&body.value)
    .bind(&body.metadata)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(rid.to_string()),
            after: Some(serde_json::to_value(&body).unwrap_or(Value::Null)),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "channel.topic_rule.create",
                "channel_topic_rule",
            )
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok", "id": rid}))))
}

async fn delete_topic_rule(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, rule_id)): Path<(String, i64)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query("DELETE FROM channel_topic_rules WHERE id=$1 AND channel_id=$2")
        .bind(rule_id)
        .bind(&channel_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Rule not found".to_string()));
    }

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(rule_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(
                &principal,
                "channel.topic_rule.delete",
                "channel_topic_rule",
            )
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

// ── References ────────────────────────────────────────────────────────────────

async fn add_reference(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<ReferenceIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let rid: i64 = sqlx::query_scalar(
        r#"INSERT INTO channel_references (channel_id, kind, label, uri, minio_key, parsed_metadata, uploaded_by)
           VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7) RETURNING id"#,
    )
    .bind(&channel_id)
    .bind(&body.kind)
    .bind(&body.label)
    .bind(&body.uri)
    .bind(&body.minio_key)
    .bind(&body.parsed_metadata)
    .bind(principal.user_id.parse::<i64>().ok())
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(rid.to_string()),
            after: Some(serde_json::to_value(&body).unwrap_or(Value::Null)),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.reference.create", "channel_reference")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok", "id": rid}))))
}

async fn delete_reference(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, ref_id)): Path<(String, i64)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query("DELETE FROM channel_references WHERE id=$1 AND channel_id=$2")
        .bind(ref_id)
        .bind(&channel_id)
        .execute(&pool)
        .await
        .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Reference not found".to_string()));
    }

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(ref_id.to_string()),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.reference.delete", "channel_reference")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

// ── Memory ────────────────────────────────────────────────────────────────────

async fn add_memory(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<MemoryIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let mid: i64 = sqlx::query_scalar(
        r#"INSERT INTO channel_memory (channel_id, memory_type, content, confidence)
           VALUES ($1,$2,$3::jsonb,$4) RETURNING id"#,
    )
    .bind(&channel_id)
    .bind(&body.memory_type)
    .bind(&body.content)
    .bind(body.confidence)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(mid.to_string()),
            after: Some(serde_json::to_value(&body).unwrap_or(Value::Null)),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.memory.add", "channel_memory")
        },
    )
    .await;

    Ok((StatusCode::OK, Json(json!({"status": "ok", "id": mid}))))
}

// ── Drafts ────────────────────────────────────────────────────────────────────

async fn create_draft(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Json(body): Json<DraftIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let did: i64 = sqlx::query_scalar(
        r#"INSERT INTO channel_drafts (user_id, current_step, payload)
           VALUES ($1,$2,$3::jsonb) RETURNING id"#,
    )
    .bind(principal.user_id.parse::<i64>().ok())
    .bind(body.current_step)
    .bind(&body.payload)
    .fetch_one(&pool)
    .await
    .map_err(ApiError::Database)?;

    Ok((StatusCode::OK, Json(json!({"status": "ok", "id": did}))))
}

async fn save_draft(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(draft_id): Path<i64>,
    Json(body): Json<DraftIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let res = sqlx::query(
        r#"UPDATE channel_drafts
              SET current_step=$1, payload=$2::jsonb, updated_at=NOW()
            WHERE id=$3 AND (user_id=$4 OR user_id IS NULL)"#,
    )
    .bind(body.current_step)
    .bind(&body.payload)
    .bind(draft_id)
    .bind(principal.user_id.parse::<i64>().ok())
    .execute(&pool)
    .await
    .map_err(ApiError::Database)?;

    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Draft not found".to_string()));
    }

    Ok((StatusCode::OK, Json(json!({"status": "ok"}))))
}

async fn get_draft(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(draft_id): Path<i64>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    let row =
        sqlx::query("SELECT id, current_step, payload, updated_at FROM channel_drafts WHERE id=$1")
            .bind(draft_id)
            .fetch_optional(&pool)
            .await
            .map_err(ApiError::Database)?
            .ok_or_else(|| ApiError::NotFound("Draft not found".to_string()))?;

    use sqlx::Row;
    Ok((
        StatusCode::OK,
        Json(json!({
            "data": {
                "id": row.try_get::<i64, _>("id").ok(),
                "current_step": row.try_get::<i32, _>("current_step").ok(),
                "payload": row.try_get::<Option<Value>, _>("payload").ok().flatten(),
                "updated_at": row.try_get::<Option<DateTime<Utc>>, _>("updated_at").ok().flatten(),
            }
        })),
    ))
}

// ── Sub-resource list endpoints ───────────────────────────────────────────────

async fn list_pillars(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query_scalar::<_, i64>("SELECT 1 FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;
    let rows = sqlx::query(
        "SELECT id, name, description, weight, examples, position \
           FROM channel_pillars WHERE channel_id=$1 ORDER BY position",
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "name": r.try_get::<Option<String>, _>("name").ok().flatten(),
                "description": r.try_get::<Option<String>, _>("description").ok().flatten(),
                "weight": r.try_get::<Option<f64>, _>("weight").ok().flatten(),
                "examples": r.try_get::<Option<Value>, _>("examples").ok().flatten(),
                "position": r.try_get::<Option<i32>, _>("position").ok().flatten(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

async fn list_topic_rules(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query_scalar::<_, i64>("SELECT 1 FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;
    let rows = sqlx::query(
        "SELECT id, kind, value, metadata, created_at \
           FROM channel_topic_rules WHERE channel_id=$1 ORDER BY kind, id",
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "kind": r.try_get::<Option<String>, _>("kind").ok().flatten(),
                "value": r.try_get::<Option<String>, _>("value").ok().flatten(),
                "metadata": r.try_get::<Option<Value>, _>("metadata").ok().flatten(),
                "created_at": r.try_get::<Option<DateTime<Utc>>, _>("created_at").ok().flatten(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

async fn list_references(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query_scalar::<_, i64>("SELECT 1 FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;
    let rows = sqlx::query(
        "SELECT id, kind, label, uri, minio_key, parsed_metadata, uploaded_at \
           FROM channel_references WHERE channel_id=$1 ORDER BY uploaded_at DESC",
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "kind": r.try_get::<Option<String>, _>("kind").ok().flatten(),
                "label": r.try_get::<Option<String>, _>("label").ok().flatten(),
                "uri": r.try_get::<Option<String>, _>("uri").ok().flatten(),
                "minio_key": r.try_get::<Option<String>, _>("minio_key").ok().flatten(),
                "parsed_metadata": r.try_get::<Option<Value>, _>("parsed_metadata").ok().flatten(),
                "uploaded_at": r.try_get::<Option<DateTime<Utc>>, _>("uploaded_at").ok().flatten(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

async fn list_memory(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    sqlx::query_scalar::<_, i64>("SELECT 1 FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;
    let rows = sqlx::query(
        "SELECT id, memory_type, content, confidence, created_at \
           FROM channel_memory WHERE channel_id=$1 ORDER BY created_at DESC LIMIT 100",
    )
    .bind(&channel_id)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "memory_type": r.try_get::<Option<String>, _>("memory_type").ok().flatten(),
                "content": r.try_get::<Option<Value>, _>("content").ok().flatten(),
                "confidence": r.try_get::<Option<f64>, _>("confidence").ok().flatten(),
                "created_at": r.try_get::<Option<DateTime<Utc>>, _>("created_at").ok().flatten(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

async fn list_drafts(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let uid = principal.user_id.parse::<i64>().ok();
    let rows = sqlx::query(
        "SELECT id, current_step, payload, updated_at \
           FROM channel_drafts WHERE user_id=$1 ORDER BY updated_at DESC",
    )
    .bind(uid)
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    use sqlx::Row;
    let data: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id": r.try_get::<i64, _>("id").ok(),
                "current_step": r.try_get::<Option<i32>, _>("current_step").ok().flatten(),
                "payload": r.try_get::<Option<Value>, _>("payload").ok().flatten(),
                "updated_at": r.try_get::<Option<DateTime<Utc>>, _>("updated_at").ok().flatten(),
            })
        })
        .collect();

    Ok((StatusCode::OK, Json(json!({"data": data}))))
}

// ── Export ────────────────────────────────────────────────────────────────────

async fn export_channel(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
) -> ApiResult<impl IntoResponse> {
    let ch = sqlx::query("SELECT * FROM channels WHERE channel_id=$1 AND workspace_id=$2")
        .bind(&channel_id)
        .bind(principal.wid)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("Channel not found".to_string()))?;

    let profile = sqlx::query("SELECT * FROM channel_profiles WHERE channel_id=$1")
        .bind(&channel_id)
        .fetch_optional(&pool)
        .await
        .map_err(ApiError::Database)?;

    let pillars =
        sqlx::query("SELECT * FROM channel_pillars WHERE channel_id=$1 ORDER BY position")
            .bind(&channel_id)
            .fetch_all(&pool)
            .await
            .map_err(ApiError::Database)?;

    let rules = sqlx::query("SELECT * FROM channel_topic_rules WHERE channel_id=$1")
        .bind(&channel_id)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

    fn row_json(r: &sqlx::postgres::PgRow) -> Value {
        use sqlx::{Column, Row};
        let mut m = serde_json::Map::new();
        for col in r.columns() {
            let n = col.name();
            let v = r
                .try_get::<Option<Value>, _>(n)
                .ok()
                .flatten()
                .or_else(|| {
                    r.try_get::<Option<String>, _>(n)
                        .ok()
                        .flatten()
                        .map(Value::String)
                })
                .or_else(|| {
                    r.try_get::<Option<i64>, _>(n)
                        .ok()
                        .flatten()
                        .map(|x| json!(x))
                })
                .or_else(|| {
                    r.try_get::<Option<bool>, _>(n)
                        .ok()
                        .flatten()
                        .map(Value::Bool)
                })
                .or_else(|| {
                    r.try_get::<Option<f64>, _>(n)
                        .ok()
                        .flatten()
                        .map(|f| json!(f))
                })
                .or_else(|| {
                    r.try_get::<Option<Vec<String>>, _>(n)
                        .ok()
                        .flatten()
                        .map(|v| json!(v))
                })
                .or_else(|| {
                    r.try_get::<Option<DateTime<Utc>>, _>(n)
                        .ok()
                        .flatten()
                        .map(|t| json!(t))
                })
                .unwrap_or(Value::Null);
            m.insert(n.to_string(), v);
        }
        Value::Object(m)
    }

    Ok((
        StatusCode::OK,
        Json(json!({
            "data": {
                "channel":     row_json(&ch),
                "profile":     profile.as_ref().map(row_json),
                "pillars":     pillars.iter().map(row_json).collect::<Vec<_>>(),
                "topic_rules": rules.iter().map(row_json).collect::<Vec<_>>(),
            }
        })),
    ))
}

// ── Field suggest (heuristic) ─────────────────────────────────────────────────
//
// Divergence: Python calls the LLM router. Rust returns heuristics only.
// Tracked in divergence_registry: channels.field_suggest.llm_vs_heuristic

async fn field_suggest(
    AuthUser(_): AuthUser,
    Json(body): Json<FieldSuggestIn>,
) -> ApiResult<impl IntoResponse> {
    let niche = body
        .context
        .get("niche")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let name = body
        .context
        .get("channel_name")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let suggestion = heuristic_suggest(&body.field, &niche, &name);

    Ok((
        StatusCode::OK,
        Json(json!({
            "data": {"suggestion": suggestion, "rationale": "heuristic"}
        })),
    ))
}

fn heuristic_suggest(field: &str, niche: &str, name: &str) -> String {
    match field {
        "mission" => format!("Make {niche} feel obvious to anyone who watches one of our videos."),
        "vision" => format!("Be the most-bingeable {niche} channel for curious beginners."),
        "brand_personality" => "Warm, sharply curious, occasionally playful.".to_string(),
        "tone" => "Direct, friendly, confident without being preachy.".to_string(),
        "narration_style" => "Conversational, fast-cut, micro-pauses for emphasis.".to_string(),
        "music_style" => "Cinematic minimal pads with subtle percussion.".to_string(),
        "humor_style" => "Dry observational, never cynical.".to_string(),
        "thumbnail_style" => "Bold subject, single contrast color, 3-word headline.".to_string(),
        "pacing_style" => "Fast (1.6 cuts/sec), slow on key facts.".to_string(),
        "lut_preference" => "Cinematic teal-orange, mild contrast.".to_string(),
        "transition_preference" => "Whip-pan + match-cut; avoid stock fades.".to_string(),
        "typography_preference" => "Inter / Geist; bold weights on emphasis words.".to_string(),
        other => format!(
            "Suggested value for {other} on {}",
            if name.is_empty() { niche } else { name }
        ),
    }
}

// ── Proxy helpers ─────────────────────────────────────────────────────────────

async fn proxy_post(
    url: &str,
    auth_header: Option<&str>,
    body: Option<Value>,
) -> ApiResult<impl IntoResponse> {
    let client = reqwest::Client::new();
    let mut req = client.post(url);
    if let Some(auth) = auth_header {
        req = req.header("Authorization", auth);
    }
    if let Some(b) = body {
        req = req.json(&b);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("proxy: {e}")))?;
    let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let body: Value = resp.json().await.unwrap_or(Value::Null);
    Ok((status, Json(body)))
}

async fn proxy_get(url: &str, auth_header: Option<&str>) -> ApiResult<impl IntoResponse> {
    let client = reqwest::Client::new();
    let mut req = client.get(url);
    if let Some(auth) = auth_header {
        req = req.header("Authorization", auth);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("proxy: {e}")))?;
    let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let body: Value = resp.json().await.unwrap_or(Value::Null);
    Ok((status, Json(body)))
}

async fn proxy_put(
    url: &str,
    auth_header: Option<&str>,
    body: Option<Value>,
) -> ApiResult<impl IntoResponse> {
    let client = reqwest::Client::new();
    let mut req = client.put(url);
    if let Some(auth) = auth_header {
        req = req.header("Authorization", auth);
    }
    if let Some(b) = body {
        req = req.json(&b);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("proxy: {e}")))?;
    let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let body: Value = resp.json().await.unwrap_or(Value::Null);
    Ok((status, Json(body)))
}

// ── Proxy endpoints ───────────────────────────────────────────────────────────

async fn proxy_trigger(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<TriggerIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;

    // Per-channel cooldown: reject if same channel was triggered within TRIGGER_COOLDOWN_SECS
    let cooldown_key = format!(
        "{}:{}",
        channel_id,
        body.content_mode.as_deref().unwrap_or("any")
    );
    {
        let mut map = trigger_cooldown_map().lock().unwrap();
        if let Some(last) = map.get(&cooldown_key) {
            let elapsed = last.elapsed();
            if elapsed < Duration::from_secs(TRIGGER_COOLDOWN_SECS) {
                let remaining = TRIGGER_COOLDOWN_SECS - elapsed.as_secs();
                return Err(ApiError::Validation(format!(
                    "Trigger cooldown active — wait {remaining}s before retrying this channel/mode."
                )));
            }
        }
        map.insert(cooldown_key, Instant::now());
    }

    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let mut payload = json!({});
    if let Some(m) = body.content_mode.as_ref() {
        payload["content_mode"] = json!(m);
    }
    if let Some(h) = body.topic_hint.as_ref() {
        payload["topic_candidates"] = json!([h]);
    }
    if !body.topic_candidates.is_empty() {
        payload["topic_candidates"] = json!(body.topic_candidates);
    }
    if let Some(c) = body.max_cost_usd {
        payload["max_cost_usd"] = json!(c);
    }

    let url = format!("{}/api/channels/{channel_id}/trigger", bff_base());
    let result = proxy_post(&url, auth.as_deref(), Some(payload.clone())).await?;

    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id.clone()),
            after: Some(payload),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.trigger", "channel")
        },
    )
    .await;

    Ok(result)
}

async fn proxy_clone(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!("{}/api/channels/{channel_id}/clone", bff_base());
    let result = proxy_post(&url, auth.as_deref(), None).await?;
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.clone", "channel")
        },
    )
    .await;
    Ok(result)
}

async fn proxy_pause_job(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, content_id)): Path<(String, String)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!(
        "{}/api/channels/{channel_id}/jobs/{content_id}/pause",
        bff_base()
    );
    let result = proxy_post(&url, auth.as_deref(), None).await?;
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(content_id),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "job.pause", "video")
        },
    )
    .await;
    Ok(result)
}

async fn proxy_resume_job(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, content_id)): Path<(String, String)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!(
        "{}/api/channels/{channel_id}/jobs/{content_id}/resume",
        bff_base()
    );
    let result = proxy_post(&url, auth.as_deref(), None).await?;
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(content_id),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "job.resume", "video")
        },
    )
    .await;
    Ok(result)
}

async fn proxy_stop_job(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path((channel_id, content_id)): Path<(String, String)>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!(
        "{}/api/channels/{channel_id}/jobs/{content_id}/stop",
        bff_base()
    );
    let result = proxy_post(&url, auth.as_deref(), None).await?;
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(content_id),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "job.stop", "video")
        },
    )
    .await;
    Ok(result)
}

async fn proxy_get_brand_kit(
    AuthUser(_): AuthUser,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
) -> ApiResult<impl IntoResponse> {
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!("{}/api/v2/channels/{channel_id}/brand-kit", bff_base());
    proxy_get(&url, auth.as_deref()).await
}

async fn proxy_put_brand_kit(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<BrandKitBindIn>,
) -> ApiResult<impl IntoResponse> {
    require_owner_or_member(&principal)?;
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let url = format!("{}/api/v2/channels/{channel_id}/brand-kit", bff_base());
    let result = proxy_put(
        &url,
        auth.as_deref(),
        Some(json!({"brand_kit_id": body.brand_kit_id})),
    )
    .await?;
    audit_log(
        &pool,
        AuditCtx {
            target_id: Some(channel_id),
            after: Some(json!({"brand_kit_id": body.brand_kit_id})),
            headers: Some(&headers),
            ..AuditCtx::new(&principal, "channel.brand_kit.bind", "channel")
        },
    )
    .await;
    Ok(result)
}

// ── F2: Cascade config resolution ────────────────────────────────────────────
//
// GET /api/v2/channels/:channel_id/resolve-config?content_mode=short
//
// Returns merged entity_settings for the 4-level hierarchy:
//   system → workspace → channel → content_mode
// Most-specific value wins (content_mode overrides channel overrides workspace
// overrides system). The response is a flat key→{value,scope} map.

#[derive(Debug, Deserialize)]
struct ResolveConfigQuery {
    content_mode: Option<String>,
}

async fn resolve_config(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Path(channel_id): Path<String>,
    Query(q): Query<ResolveConfigQuery>,
) -> ApiResult<impl IntoResponse> {
    // Verify channel belongs to this workspace
    let exists = sqlx::query(
        "SELECT 1 FROM channels WHERE channel_id=$1 AND workspace_id=$2",
    )
    .bind(&channel_id)
    .bind(principal.wid)
    .fetch_optional(&pool)
    .await
    .map_err(ApiError::Database)?;

    if exists.is_none() {
        return Err(ApiError::NotFound("Channel not found".to_string()));
    }

    let content_mode_scope_id = q
        .content_mode
        .as_deref()
        .map(|cm| format!("{}:{}", channel_id, cm));

    // Query all 4 scope levels in one pass, ordered by specificity (system=0 … content_mode=3)
    let scope_id_str = principal.wid.to_string();
    let rows = sqlx::query(
        r#"SELECT key, value,
                  CASE scope
                      WHEN 'system'       THEN 0
                      WHEN 'workspace'    THEN 1
                      WHEN 'channel'      THEN 2
                      WHEN 'content_mode' THEN 3
                      ELSE 1
                  END AS priority,
                  scope
             FROM entity_settings
            WHERE (scope = 'system'       AND scope_id = 'global')
               OR (scope = 'workspace'    AND scope_id = $1)
               OR (scope = 'channel'      AND scope_id = $2)
               OR (scope = 'content_mode' AND scope_id = $3)
            ORDER BY priority ASC"#,
    )
    .bind(&scope_id_str)
    .bind(&channel_id)
    .bind(content_mode_scope_id.as_deref().unwrap_or("__none__"))
    .fetch_all(&pool)
    .await
    .map_err(ApiError::Database)?;

    // Merge: later rows (higher priority) overwrite earlier ones
    let mut resolved: std::collections::HashMap<String, Value> =
        std::collections::HashMap::new();

    for row in &rows {
        use sqlx::Row;
        let key: String = row.get("key");
        let value: Value = row.get("value");
        let scope: String = row.get("scope");
        resolved.insert(key, json!({ "value": value, "scope": scope }));
    }

    Ok(Json(json!({
        "channel_id":   channel_id,
        "content_mode": q.content_mode,
        "resolved":     resolved,
    })))
}

// ── F3: System-level provider chain resolver ──────────────────────────────────
//
// GET /api/v2/workspace/resolve-provider-chain?category=llm&content_mode=short
//
// Returns the effective ordered provider chain for a given (category, content_mode)
// respecting the fallback hierarchy:
//   content_mode-scoped channel chain
//     → channel-scoped chain
//     → workspace chain
//     → system chain (F3 addition — ultimate fallback)

#[derive(Debug, Deserialize)]
struct ResolveChainQuery {
    category: String,
    content_mode: Option<String>,
    channel_id: Option<String>,
}

async fn resolve_provider_chain(
    AuthUser(principal): AuthUser,
    State(pool): State<PgPool>,
    Query(q): Query<ResolveChainQuery>,
) -> ApiResult<impl IntoResponse> {
    // Build candidate queries from most-specific to least-specific.
    // We pick the first scope level that has at least one row.

    struct ScopeAttempt {
        scope: &'static str,
        scope_id: Option<String>,
        workspace_id: Option<i64>,
        content_mode: Option<String>,
    }

    let attempts: Vec<ScopeAttempt> = {
        let mut v = Vec::new();

        // 1. channel + content_mode (most specific)
        if let (Some(ref cid), Some(ref cm)) = (&q.channel_id, &q.content_mode) {
            v.push(ScopeAttempt {
                scope: "channel",
                scope_id: Some(cid.clone()),
                workspace_id: Some(principal.wid),
                content_mode: Some(cm.clone()),
            });
        }
        // 2. channel-only
        if let Some(ref cid) = q.channel_id {
            v.push(ScopeAttempt {
                scope: "channel",
                scope_id: Some(cid.clone()),
                workspace_id: Some(principal.wid),
                content_mode: None,
            });
        }
        // 3. workspace + content_mode
        if let Some(ref cm) = q.content_mode {
            v.push(ScopeAttempt {
                scope: "workspace",
                scope_id: None,
                workspace_id: Some(principal.wid),
                content_mode: Some(cm.clone()),
            });
        }
        // 4. workspace-only
        v.push(ScopeAttempt {
            scope: "workspace",
            scope_id: None,
            workspace_id: Some(principal.wid),
            content_mode: None,
        });
        // 5. system + content_mode  (F3)
        if let Some(ref cm) = q.content_mode {
            v.push(ScopeAttempt {
                scope: "system",
                scope_id: None,
                workspace_id: None,
                content_mode: Some(cm.clone()),
            });
        }
        // 6. system-only  (F3 ultimate fallback)
        v.push(ScopeAttempt {
            scope: "system",
            scope_id: None,
            workspace_id: None,
            content_mode: None,
        });
        v
    };

    for attempt in &attempts {
        let rows = sqlx::query(
            r#"SELECT cv2.id, pc.provider, pc.model, cv2.position, cv2.fallback_strategy,
                      cv2.scope, cv2.content_mode, cv2.is_enabled
                 FROM provider_chains_v2 cv2
                 JOIN provider_credentials pc ON pc.id = cv2.credential_id
                WHERE cv2.category    = $1
                  AND cv2.scope       = $2
                  AND (cv2.scope_id       IS NOT DISTINCT FROM $3)
                  AND (cv2.workspace_id   IS NOT DISTINCT FROM $4)
                  AND (cv2.content_mode   IS NOT DISTINCT FROM $5)
                  AND cv2.is_enabled  = TRUE
                  AND pc.enabled      = TRUE
                ORDER BY cv2.position ASC"#,
        )
        .bind(&q.category)
        .bind(attempt.scope)
        .bind(&attempt.scope_id)
        .bind(attempt.workspace_id)
        .bind(&attempt.content_mode)
        .fetch_all(&pool)
        .await
        .map_err(ApiError::Database)?;

        if rows.is_empty() {
            continue;
        }

        use sqlx::Row;
        let chain: Vec<Value> = rows
            .iter()
            .map(|r| {
                json!({
                    "id":               r.get::<i64, _>("id"),
                    "provider":         r.get::<String, _>("provider"),
                    "model":            r.get::<Option<String>, _>("model"),
                    "position":         r.get::<i32, _>("position"),
                    "fallback_strategy":r.get::<String, _>("fallback_strategy"),
                    "scope":            r.get::<String, _>("scope"),
                    "content_mode":     r.get::<Option<String>, _>("content_mode"),
                })
            })
            .collect();

        return Ok(Json(json!({
            "category":     q.category,
            "content_mode": q.content_mode,
            "scope_used":   attempt.scope,
            "chain":        chain,
        })));
    }

    // No chain found at any scope level
    Ok(Json(json!({
        "category":     q.category,
        "content_mode": q.content_mode,
        "scope_used":   null,
        "chain":        [],
    })))
}
