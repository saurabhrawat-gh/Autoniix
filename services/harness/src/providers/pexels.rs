//! Pexels stock photo API mock.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize)]
pub struct PexelsRequest {
    pub query: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub per_page: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page: Option<u32>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PexelsResponse {
    pub page: u32,
    pub per_page: u32,
    pub photos: Vec<PexelsPhoto>,
    pub total_results: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PexelsPhoto {
    pub id: String,
    pub width: u32,
    pub height: u32,
    pub url: String,
    pub photographer: String,
    pub src: PexelsSrc,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PexelsSrc {
    pub original: String,
    pub large: String,
    pub medium: String,
    pub small: String,
}

/// Mock Pexels photo search.
pub fn search_photos(cache: &ProviderCache, req: &PexelsRequest) -> PexelsResponse {
    let key = ProviderCache::key("pexels", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let per_page = req.per_page.unwrap_or(15).min(5); // cap mock at 5
    let photos = (0..per_page)
        .map(|i| PexelsPhoto {
            id: format!("mock_pexels_{i}"),
            width: 1920,
            height: 1080,
            url: format!("https://www.pexels.com/photo/mock-{i}/"),
            photographer: "Mock Photographer".into(),
            src: PexelsSrc {
                original: format!("https://images.pexels.com/photos/{i}/original.jpeg"),
                large: format!("https://images.pexels.com/photos/{i}/large.jpeg"),
                medium: format!("https://images.pexels.com/photos/{i}/medium.jpeg"),
                small: format!("https://images.pexels.com/photos/{i}/small.jpeg"),
            },
        })
        .collect();

    let resp = PexelsResponse {
        page: req.page.unwrap_or(1),
        per_page,
        photos,
        total_results: 1000,
    };
    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_search_photos() {
        let cache = ProviderCache::new(tempdir().unwrap().keep(), true);
        let req = PexelsRequest {
            query: "nature".into(),
            per_page: Some(10),
            page: None,
        };
        let resp = search_photos(&cache, &req);
        assert!(!resp.photos.is_empty());
        assert!(resp.total_results > 0);
        assert!(resp.photos[0].src.original.starts_with("https://"));
    }
}
