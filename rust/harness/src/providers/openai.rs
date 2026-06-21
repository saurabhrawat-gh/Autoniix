//! OpenAI API mock — GPT-4, GPT-4o, GPT-3.5, embeddings.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatResponse {
    pub id: String,
    pub object: String,
    pub created: i64,
    pub model: String,
    pub choices: Vec<ChatChoice>,
    pub usage: TokenUsage,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatChoice {
    pub index: u32,
    pub message: ChatMessage,
    pub finish_reason: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TokenUsage {
    pub prompt_tokens: u32,
    pub completion_tokens: u32,
    pub total_tokens: u32,
}

/// Mock OpenAI chat completion.
pub fn chat_completion(cache: &ProviderCache, req: &ChatRequest) -> ChatResponse {
    let key = ProviderCache::key("openai", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let content = generate_content(req);
    let prompt_tokens = req
        .messages
        .iter()
        .map(|m| word_count(&m.content))
        .sum::<u32>();
    let completion_tokens = word_count(&content);

    let resp = ChatResponse {
        id: format!("chatcmpl-mock-{key}"),
        object: "chat.completion".into(),
        created: chrono::Utc::now().timestamp(),
        model: req.model.clone(),
        choices: vec![ChatChoice {
            index: 0,
            message: ChatMessage {
                role: "assistant".into(),
                content,
            },
            finish_reason: "stop".into(),
        }],
        usage: TokenUsage {
            prompt_tokens,
            completion_tokens,
            total_tokens: prompt_tokens + completion_tokens,
        },
    };

    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

fn generate_content(req: &ChatRequest) -> String {
    let prompt: String = req
        .messages
        .iter()
        .map(|m| m.content.as_str())
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase();

    // JSON format requested
    if req
        .response_format
        .as_ref()
        .and_then(|f| f.get("type"))
        .and_then(|t| t.as_str())
        == Some("json_object")
    {
        if prompt.contains("research") {
            return json!({
                "selected_topic": "Mock Research Topic",
                "title_candidates": ["Mock Title 1", "Mock Title 2"],
                "key_facts": ["Fact 1: data shows 80% improvement", "Fact 2: adopted by 500+ companies"],
                "sources": [{"url": "https://example.com", "title": "Mock Source"}]
            }).to_string();
        }
        if prompt.contains("script") {
            return json!({
                "title": "Mock Video Title",
                "segments": [{"id": "seg_1", "section": "hook", "text": "Mock hook text.", "duration_s": 5}],
                "total_duration_s": 60
            }).to_string();
        }
        return json!({"result": "mock_response", "status": "success"}).to_string();
    }

    "Mock OpenAI response. The harness intercepted this call — no real API was contacted.".into()
}

fn word_count(s: &str) -> u32 {
    (s.split_whitespace().count() as f32 * 1.3) as u32
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn cache() -> ProviderCache {
        ProviderCache::new(tempdir().unwrap().into_path(), true)
    }

    #[test]
    fn test_chat_completion_returns_valid_response() {
        let c = cache();
        let req = ChatRequest {
            model: "gpt-4o".into(),
            messages: vec![ChatMessage {
                role: "user".into(),
                content: "Hello".into(),
            }],
            max_tokens: Some(100),
            temperature: None,
            response_format: None,
        };
        let resp = chat_completion(&c, &req);
        assert_eq!(resp.object, "chat.completion");
        assert_eq!(resp.model, "gpt-4o");
        assert!(!resp.choices.is_empty());
        assert!(resp.usage.total_tokens > 0);
    }

    #[test]
    fn test_chat_completion_json_format() {
        let c = cache();
        let req = ChatRequest {
            model: "gpt-4o-mini".into(),
            messages: vec![ChatMessage {
                role: "user".into(),
                content: "research topic".into(),
            }],
            max_tokens: None,
            temperature: None,
            response_format: Some(json!({"type": "json_object"})),
        };
        let resp = chat_completion(&c, &req);
        let content = &resp.choices[0].message.content;
        let parsed: Value = serde_json::from_str(content).expect("should be valid JSON");
        assert!(parsed.get("selected_topic").is_some());
    }

    #[test]
    fn test_cache_hit() {
        let c = cache();
        let req = ChatRequest {
            model: "gpt-4o".into(),
            messages: vec![ChatMessage {
                role: "user".into(),
                content: "cache test".into(),
            }],
            max_tokens: None,
            temperature: None,
            response_format: None,
        };
        let r1 = chat_completion(&c, &req);
        let r2 = chat_completion(&c, &req);
        assert_eq!(r1.id, r2.id);
    }
}
