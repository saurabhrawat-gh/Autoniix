//! Google Gemini API mock.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiPart {
    pub text: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiContent {
    pub parts: Vec<GeminiPart>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiRequest {
    pub contents: Vec<GeminiContent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiResponse {
    pub candidates: Vec<GeminiCandidate>,
    #[serde(rename = "usageMetadata")]
    pub usage_metadata: GeminiUsage,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiCandidate {
    pub content: GeminiContent,
    #[serde(rename = "finishReason")]
    pub finish_reason: String,
    #[serde(rename = "safetyRatings")]
    pub safety_ratings: Vec<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GeminiUsage {
    #[serde(rename = "promptTokenCount")]
    pub prompt_token_count: u32,
    #[serde(rename = "candidatesTokenCount")]
    pub candidates_token_count: u32,
    #[serde(rename = "totalTokenCount")]
    pub total_token_count: u32,
}

/// Mock Gemini generate content.
pub fn generate_content(cache: &ProviderCache, req: &GeminiRequest) -> GeminiResponse {
    let key = ProviderCache::key("gemini", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let prompt: String = req
        .contents
        .iter()
        .flat_map(|c| c.parts.iter().map(|p| p.text.as_str()))
        .collect::<Vec<_>>()
        .join(" ");

    let response_text = format!(
        "Mock Gemini response for: {}. No real API was contacted.",
        &prompt[..prompt.len().min(80)]
    );

    let prompt_tokens = (prompt.split_whitespace().count() as f32 * 1.3) as u32;
    let candidates_tokens = (response_text.split_whitespace().count() as f32 * 1.3) as u32;

    let resp = GeminiResponse {
        candidates: vec![GeminiCandidate {
            content: GeminiContent {
                parts: vec![GeminiPart {
                    text: response_text,
                }],
                role: Some("model".into()),
            },
            finish_reason: "STOP".into(),
            safety_ratings: vec![serde_json::json!({
                "category": "HARM_CATEGORY_HARASSMENT",
                "probability": "NEGLIGIBLE"
            })],
        }],
        usage_metadata: GeminiUsage {
            prompt_token_count: prompt_tokens,
            candidates_token_count: candidates_tokens,
            total_token_count: prompt_tokens + candidates_tokens,
        },
    };

    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_generate_content() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = GeminiRequest {
            contents: vec![GeminiContent {
                parts: vec![GeminiPart {
                    text: "Explain neural networks.".into(),
                }],
                role: Some("user".into()),
            }],
            model: Some("gemini-1.5-pro".into()),
        };
        let resp = generate_content(&cache, &req);
        assert!(!resp.candidates.is_empty());
        assert_eq!(resp.candidates[0].finish_reason, "STOP");
        assert!(!resp.candidates[0].content.parts.is_empty());
        assert!(resp.usage_metadata.total_token_count > 0);
    }
}
