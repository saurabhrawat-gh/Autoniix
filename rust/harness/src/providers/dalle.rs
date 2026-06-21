//! DALL-E image generation mock — returns a 1×1 transparent PNG.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ResponseFormat {
    Url,
    B64Json,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DalleRequest {
    pub prompt: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<ResponseFormat>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DalleResponse {
    pub created: i64,
    pub data: Vec<DalleImage>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DalleImage {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub b64_json: Option<String>,
}

/// Minimal valid 1×1 transparent PNG (base64).
const PLACEHOLDER_PNG_B64: &str =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

/// Mock DALL-E image generation.
pub fn generate(cache: &ProviderCache, req: &DalleRequest) -> DalleResponse {
    let key = ProviderCache::key("dalle", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let use_b64 = req.response_format == Some(ResponseFormat::B64Json);
    let image = if use_b64 {
        DalleImage {
            url: None,
            b64_json: Some(PLACEHOLDER_PNG_B64.to_string()),
        }
    } else {
        DalleImage {
            url: Some(format!("https://mock-dalle.example.com/images/{key}.png")),
            b64_json: None,
        }
    };

    let resp = DalleResponse {
        created: chrono::Utc::now().timestamp(),
        data: vec![image],
    };
    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_generate_url_format() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = DalleRequest {
            prompt: "A futuristic city".into(),
            size: Some("1024x1024".into()),
            model: Some("dall-e-3".into()),
            response_format: Some(ResponseFormat::Url),
        };
        let resp = generate(&cache, &req);
        assert!(!resp.data.is_empty());
        assert!(resp.data[0].url.is_some());
        assert!(resp.data[0].b64_json.is_none());
    }

    #[test]
    fn test_generate_b64_format() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = DalleRequest {
            prompt: "Abstract art".into(),
            size: None,
            model: None,
            response_format: Some(ResponseFormat::B64Json),
        };
        let resp = generate(&cache, &req);
        let b64 = resp.data[0].b64_json.as_ref().unwrap();
        // Verify it decodes to valid bytes
        let decoded = base64::decode(b64).unwrap();
        assert!(!decoded.is_empty());
    }
}
