//! F7: ElevenLabs voice proxy endpoints
//!
//! Two endpoints, both auth-gated (any workspace member):
//!
//!   GET  /api/v2/voice/voices   — list voices from ElevenLabs (or empty if key absent)
//!   POST /api/v2/voice/preview  — synthesise a short sample, returns base64 MP3

use axum::{
    extract::State,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

const ELEVEN_BASE: &str = "https://api.elevenlabs.io/v1";
const PREVIEW_CHAR_LIMIT: usize = 250;

fn eleven_key() -> Option<String> {
    std::env::var("ELEVENLABS_API_KEY").ok()
}

fn eleven_model() -> String {
    std::env::var("ELEVENLABS_MODEL_ID").unwrap_or_else(|_| "eleven_multilingual_v2".to_string())
}

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/voice/voices", get(list_voices))
        .route("/api/v2/voice/preview", post(preview_voice))
        .with_state(pool)
}

#[derive(Debug, Serialize)]
struct VoiceItem {
    voice_id: String,
    name: String,
    category: Option<String>,
    preview_url: Option<String>,
}

#[utoipa::path(
    get,
    path = "/api/v2/voice/voices",
    tag = "voice",
    responses((status = 200, description = "List of ElevenLabs voices")),
    security(("cookie_auth" = []))
)]
pub(crate) async fn list_voices(
    AuthUser(_principal): AuthUser,
    State(_pool): State<PgPool>,
) -> ApiResult<impl IntoResponse> {
    let Some(api_key) = eleven_key() else {
        return Ok(Json(
            json!({ "data": [], "warning": "ELEVENLABS_API_KEY not configured" }),
        ));
    };

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| ApiError::Internal(e.to_string()))?;

    let resp = client
        .get(format!("{ELEVEN_BASE}/voices"))
        .header("xi-api-key", &api_key)
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("ElevenLabs voices request failed: {e}")))?;

    if !resp.status().is_success() {
        let status = resp.status().as_u16();
        let body = resp.text().await.unwrap_or_default();
        return Err(ApiError::Internal(format!(
            "ElevenLabs voices API error {status}: {body}"
        )));
    }

    let body: Value = resp
        .json()
        .await
        .map_err(|e| ApiError::Internal(format!("ElevenLabs voices parse error: {e}")))?;

    let voices: Vec<VoiceItem> = body
        .get("voices")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(|v| {
                    Some(VoiceItem {
                        voice_id: v.get("voice_id")?.as_str()?.to_string(),
                        name: v.get("name")?.as_str()?.to_string(),
                        category: v.get("category").and_then(Value::as_str).map(String::from),
                        preview_url: v
                            .get("preview_url")
                            .and_then(Value::as_str)
                            .map(String::from),
                    })
                })
                .collect()
        })
        .unwrap_or_default();

    Ok(Json(json!({ "data": voices })))
}

#[derive(Debug, Deserialize)]
struct PreviewRequest {
    voice_id: String,
    /// Text to synthesise. Capped at PREVIEW_CHAR_LIMIT chars.
    text: Option<String>,
    stability: Option<f64>,
    similarity_boost: Option<f64>,
    style: Option<f64>,
}

#[utoipa::path(
    post,
    path = "/api/v2/voice/preview",
    tag = "voice",
    responses((status = 200, description = "Base64-encoded MP3 sample")),
    security(("cookie_auth" = []))
)]
pub(crate) async fn preview_voice(
    AuthUser(_principal): AuthUser,
    State(_pool): State<PgPool>,
    Json(body): Json<PreviewRequest>,
) -> ApiResult<impl IntoResponse> {
    let Some(api_key) = eleven_key() else {
        return Err(ApiError::Internal(
            "ELEVENLABS_API_KEY is not configured on this server".to_string(),
        ));
    };

    let raw_text = body.text.unwrap_or_else(|| {
        "Welcome to the channel. Today we explore something truly fascinating.".to_string()
    });
    let text: String = raw_text.chars().take(PREVIEW_CHAR_LIMIT).collect();

    let voice_settings = json!({
        "stability":        body.stability.unwrap_or(0.50),
        "similarity_boost": body.similarity_boost.unwrap_or(0.75),
        "style":            body.style.unwrap_or(0.40),
        "use_speaker_boost": true,
    });

    let payload = json!({
        "text":          text,
        "model_id":      eleven_model(),
        "voice_settings": voice_settings,
        "output_format": "mp3_44100_128",
    });

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| ApiError::Internal(e.to_string()))?;

    let resp = client
        .post(format!("{ELEVEN_BASE}/text-to-speech/{}", body.voice_id))
        .header("xi-api-key", &api_key)
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .map_err(|e| ApiError::Internal(format!("ElevenLabs TTS request failed: {e}")))?;

    if !resp.status().is_success() {
        let status = resp.status().as_u16();
        let err_body = resp.text().await.unwrap_or_default();
        return Err(ApiError::Internal(format!(
            "ElevenLabs TTS error {status}: {err_body}"
        )));
    }

    let audio_bytes = resp
        .bytes()
        .await
        .map_err(|e| ApiError::Internal(format!("ElevenLabs audio read error: {e}")))?;

    let data_url = format!("data:audio/mpeg;base64,{}", B64.encode(&audio_bytes));

    Ok(Json(json!({
        "voice_id":  body.voice_id,
        "data_url":  data_url,
        "chars":     text.len(),
    })))
}
