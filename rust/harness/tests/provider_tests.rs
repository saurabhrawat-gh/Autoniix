//! Integration tests for provider mocks.
//! Run with: cargo test -p harness

use harness::providers::{
    anthropic, dalle, fish_audio, gemini, openai, pexels, pixabay, serpapi, youtube, ProviderCache,
};
use tempfile::tempdir;

fn cache() -> ProviderCache {
    ProviderCache::new(tempdir().unwrap().into_path(), true)
}

// ── OpenAI ──────────────────────────────────────────────────────────────────

#[test]
fn test_openai_chat_completion() {
    let c = cache();
    let req = openai::ChatRequest {
        model: "gpt-4o".into(),
        messages: vec![openai::ChatMessage { role: "user".into(), content: "Hello, world!".into() }],
        max_tokens: Some(100),
        temperature: None,
        response_format: None,
    };
    let resp = openai::chat_completion(&c, &req);
    assert_eq!(resp.object, "chat.completion");
    assert_eq!(resp.model, "gpt-4o");
    assert!(!resp.choices.is_empty());
    assert_eq!(resp.choices[0].message.role, "assistant");
    assert!(resp.usage.total_tokens > 0);
}

#[test]
fn test_openai_json_format_research() {
    let c = cache();
    let req = openai::ChatRequest {
        model: "gpt-4o-mini".into(),
        messages: vec![openai::ChatMessage {
            role: "user".into(),
            content: "generate research data for AI topic".into(),
        }],
        max_tokens: None,
        temperature: None,
        response_format: Some(serde_json::json!({"type": "json_object"})),
    };
    let resp = openai::chat_completion(&c, &req);
    let content = &resp.choices[0].message.content;
    let parsed: serde_json::Value = serde_json::from_str(content).expect("must be JSON");
    assert!(parsed.get("selected_topic").is_some());
}

#[test]
fn test_openai_cache_hit_returns_same_id() {
    let c = cache();
    let req = openai::ChatRequest {
        model: "gpt-4o".into(),
        messages: vec![openai::ChatMessage { role: "user".into(), content: "cache test".into() }],
        max_tokens: None,
        temperature: None,
        response_format: None,
    };
    let r1 = openai::chat_completion(&c, &req);
    let r2 = openai::chat_completion(&c, &req);
    assert_eq!(r1.id, r2.id);
}

// ── Anthropic ────────────────────────────────────────────────────────────────

#[test]
fn test_anthropic_message() {
    let c = cache();
    let req = anthropic::AnthropicRequest {
        model: "claude-3-5-sonnet-20241022".into(),
        messages: vec![anthropic::AnthropicMessage {
            role: "user".into(),
            content: "Explain quantum computing.".into(),
        }],
        max_tokens: 200,
        system: None,
    };
    let resp = anthropic::create_message(&c, &req);
    assert_eq!(resp.kind, "message");
    assert_eq!(resp.role, "assistant");
    assert!(!resp.content.is_empty());
    assert_eq!(resp.content[0].kind, "text");
    assert!(!resp.content[0].text.is_empty());
}

// ── Fish Audio ───────────────────────────────────────────────────────────────

#[test]
fn test_fish_audio_returns_valid_wav() {
    let c = cache();
    let req = fish_audio::FishAudioRequest {
        text: "Hello, this is a test narration for the harness.".into(),
        voice_id: "voice_001".into(),
        speed: None,
        format: None,
    };
    let wav = fish_audio::synthesize(&c, &req);
    assert!(wav.starts_with(b"RIFF"), "WAV must start with RIFF");
    assert_eq!(&wav[8..12], b"WAVE", "WAV must contain WAVE");
    assert!(wav.len() > 44, "WAV must have audio data beyond header");
}

// ── DALL-E ───────────────────────────────────────────────────────────────────

#[test]
fn test_dalle_url_format() {
    let c = cache();
    let req = dalle::DalleRequest {
        prompt: "A futuristic skyline at dusk".into(),
        size: Some("1024x1024".into()),
        model: Some("dall-e-3".into()),
        response_format: Some(dalle::ResponseFormat::Url),
    };
    let resp = dalle::generate(&c, &req);
    assert!(!resp.data.is_empty());
    assert!(resp.data[0].url.is_some());
    assert!(resp.data[0].b64_json.is_none());
}

#[test]
fn test_dalle_b64_format_decodes() {
    let c = cache();
    let req = dalle::DalleRequest {
        prompt: "Abstract digital art".into(),
        size: None,
        model: None,
        response_format: Some(dalle::ResponseFormat::B64Json),
    };
    let resp = dalle::generate(&c, &req);
    let b64 = resp.data[0].b64_json.as_ref().expect("b64_json must be present");
    let decoded = base64::decode(b64).expect("must be valid base64");
    assert!(!decoded.is_empty());
}

// ── Pexels ───────────────────────────────────────────────────────────────────

#[test]
fn test_pexels_search() {
    let c = cache();
    let req = pexels::PexelsRequest { query: "ocean waves".into(), per_page: Some(10), page: None };
    let resp = pexels::search_photos(&c, &req);
    assert!(!resp.photos.is_empty());
    assert!(resp.total_results > 0);
    assert!(resp.photos[0].src.original.starts_with("https://"));
    assert!(!resp.photos[0].photographer.is_empty());
}

// ── Pixabay ──────────────────────────────────────────────────────────────────

#[test]
fn test_pixabay_search() {
    let c = cache();
    let req = pixabay::PixabayRequest {
        q: "technology".into(),
        per_page: Some(15),
        page: None,
        image_type: Some("photo".into()),
    };
    let resp = pixabay::search_images(&c, &req);
    assert!(!resp.hits.is_empty());
    assert_eq!(resp.hits[0].kind, "photo");
    assert!(resp.total_hits > 0);
}

// ── SerpAPI ──────────────────────────────────────────────────────────────────

#[test]
fn test_serpapi_search() {
    let c = cache();
    let req = serpapi::SerpApiRequest {
        q: "artificial intelligence trends 2024".into(),
        num: Some(10),
        gl: None,
        hl: None,
    };
    let resp = serpapi::search(&c, &req);
    assert_eq!(resp.search_metadata.status, "Success");
    assert!(!resp.organic_results.is_empty());
    assert_eq!(resp.organic_results[0].position, 1);
    assert!(resp.organic_results[0].link.starts_with("https://"));
    assert!(!resp.organic_results[0].snippet.is_empty());
}

// ── YouTube ──────────────────────────────────────────────────────────────────

#[test]
fn test_youtube_search() {
    let c = cache();
    let req = youtube::YouTubeSearchRequest {
        q: "machine learning for beginners".into(),
        max_results: Some(5),
        part: None,
    };
    let resp = youtube::search(&c, &req);
    assert_eq!(resp.kind, "youtube#searchListResponse");
    assert!(!resp.items.is_empty());
    assert_eq!(resp.items[0]["id"]["kind"], "youtube#video");
    assert!(resp.items[0]["snippet"]["title"].is_string());
}

#[test]
fn test_youtube_video_details() {
    let c = cache();
    let req = youtube::YouTubeVideoRequest { id: "dQw4w9WgXcQ".into(), part: None };
    let resp = youtube::video_details(&c, &req);
    assert_eq!(resp.kind, "youtube#videoListResponse");
    assert_eq!(resp.items[0]["id"], "dQw4w9WgXcQ");
    assert!(resp.items[0]["statistics"]["viewCount"].is_string());
}

// ── Gemini ───────────────────────────────────────────────────────────────────

#[test]
fn test_gemini_generate_content() {
    let c = cache();
    let req = gemini::GeminiRequest {
        contents: vec![gemini::GeminiContent {
            parts: vec![gemini::GeminiPart { text: "Explain neural networks briefly.".into() }],
            role: Some("user".into()),
        }],
        model: Some("gemini-1.5-pro".into()),
    };
    let resp = gemini::generate_content(&c, &req);
    assert!(!resp.candidates.is_empty());
    assert_eq!(resp.candidates[0].finish_reason, "STOP");
    assert!(!resp.candidates[0].content.parts.is_empty());
    assert!(resp.usage_metadata.total_token_count > 0);
}

// ── Cache disabled ────────────────────────────────────────────────────────────

#[test]
fn test_cache_disabled_writes_no_files() {
    let dir = tempdir().unwrap();
    let c = ProviderCache::new(dir.path(), false);
    let req = openai::ChatRequest {
        model: "gpt-4o".into(),
        messages: vec![openai::ChatMessage { role: "user".into(), content: "no cache".into() }],
        max_tokens: None,
        temperature: None,
        response_format: None,
    };
    openai::chat_completion(&c, &req);
    let files: Vec<_> = std::fs::read_dir(dir.path()).unwrap().collect();
    assert!(files.is_empty(), "cache disabled should write no files");
}
