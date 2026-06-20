//! SerpAPI web search mock.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize)]
pub struct SerpApiRequest {
    pub q: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub num: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gl: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hl: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SerpApiResponse {
    pub search_metadata: SearchMetadata,
    pub search_parameters: serde_json::Value,
    pub organic_results: Vec<OrganicResult>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchMetadata {
    pub id: String,
    pub status: String,
    pub created_at: String,
    pub total_time_taken: f32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OrganicResult {
    pub position: u32,
    pub title: String,
    pub link: String,
    pub snippet: String,
    pub source: String,
}

/// Mock SerpAPI search.
pub fn search(cache: &ProviderCache, req: &SerpApiRequest) -> SerpApiResponse {
    let key = ProviderCache::key("serpapi", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let num = req.num.unwrap_or(10).min(5);
    let organic_results = (0..num)
        .map(|i| OrganicResult {
            position: i + 1,
            title: format!("Mock Result {} for: {}", i + 1, req.q),
            link: format!("https://example.com/result-{}", i + 1),
            snippet: format!(
                "This is a mock search result snippet for query: {}. It contains relevant information.",
                req.q
            ),
            source: "Example.com".into(),
        })
        .collect();

    let now = chrono::Utc::now().to_rfc3339();
    let resp = SerpApiResponse {
        search_metadata: SearchMetadata {
            id: format!("mock_{}", chrono::Utc::now().timestamp()),
            status: "Success".into(),
            created_at: now.clone(),
            total_time_taken: 0.42,
        },
        search_parameters: serde_json::json!({"q": req.q, "num": num}),
        organic_results,
    };

    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_search() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = SerpApiRequest {
            q: "artificial intelligence 2024".into(),
            num: Some(10),
            gl: None,
            hl: None,
        };
        let resp = search(&cache, &req);
        assert_eq!(resp.search_metadata.status, "Success");
        assert!(!resp.organic_results.is_empty());
        assert!(resp.organic_results[0].position == 1);
        assert!(resp.organic_results[0].link.starts_with("https://"));
    }
}
