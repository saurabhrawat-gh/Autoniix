//! Anthropic Claude API mock.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AnthropicMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnthropicRequest {
    pub model: String,
    pub messages: Vec<AnthropicMessage>,
    pub max_tokens: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnthropicResponse {
    pub id: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub role: String,
    pub content: Vec<AnthropicContent>,
    pub model: String,
    pub stop_reason: String,
    pub usage: AnthropicUsage,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnthropicContent {
    #[serde(rename = "type")]
    pub kind: String,
    pub text: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnthropicUsage {
    pub input_tokens: u32,
    pub output_tokens: u32,
}

/// Mock Anthropic message creation.
pub fn create_message(cache: &ProviderCache, req: &AnthropicRequest) -> AnthropicResponse {
    let key = ProviderCache::key("anthropic", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let prompt: String = req
        .messages
        .iter()
        .map(|m| m.content.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    let text = format!(
        "Mock Claude response for: {}. No real API was contacted.",
        &prompt[..prompt.len().min(80)]
    );
    let input_tokens = (prompt.split_whitespace().count() as f32 * 1.3) as u32;
    let output_tokens = (text.split_whitespace().count() as f32 * 1.3) as u32;

    let resp = AnthropicResponse {
        id: format!("msg_mock-{key}"),
        kind: "message".into(),
        role: "assistant".into(),
        content: vec![AnthropicContent {
            kind: "text".into(),
            text,
        }],
        model: req.model.clone(),
        stop_reason: "end_turn".into(),
        usage: AnthropicUsage {
            input_tokens,
            output_tokens,
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
    fn test_create_message() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = AnthropicRequest {
            model: "claude-3-5-sonnet-20241022".into(),
            messages: vec![AnthropicMessage {
                role: "user".into(),
                content: "Explain AI.".into(),
            }],
            max_tokens: 200,
            system: None,
        };
        let resp = create_message(&cache, &req);
        assert_eq!(resp.kind, "message");
        assert_eq!(resp.role, "assistant");
        assert!(!resp.content.is_empty());
        assert_eq!(resp.content[0].kind, "text");
    }
}
