//! Pixabay stock media API mock.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize)]
pub struct PixabayRequest {
    pub q: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub per_page: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_type: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PixabayResponse {
    pub total: u64,
    #[serde(rename = "totalHits")]
    pub total_hits: u64,
    pub hits: Vec<PixabayHit>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PixabayHit {
    pub id: String,
    #[serde(rename = "pageURL")]
    pub page_url: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub tags: String,
    #[serde(rename = "previewURL")]
    pub preview_url: String,
    #[serde(rename = "webformatURL")]
    pub webformat_url: String,
    #[serde(rename = "largeImageURL")]
    pub large_image_url: String,
    #[serde(rename = "imageWidth")]
    pub image_width: u32,
    #[serde(rename = "imageHeight")]
    pub image_height: u32,
    pub user: String,
}

/// Mock Pixabay image search.
pub fn search_images(cache: &ProviderCache, req: &PixabayRequest) -> PixabayResponse {
    let key = ProviderCache::key("pixabay", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let per_page = req.per_page.unwrap_or(20).min(5);
    let hits = (0..per_page)
        .map(|i| PixabayHit {
            id: format!("mock_pixabay_{i}"),
            page_url: format!("https://pixabay.com/photos/mock-{i}/"),
            kind: "photo".into(),
            tags: req.q.clone(),
            preview_url: format!("https://cdn.pixabay.com/photo/mock-{i}_150.jpg"),
            webformat_url: format!("https://pixabay.com/get/mock-{i}.jpg"),
            large_image_url: format!("https://pixabay.com/get/mock-{i}_1920.jpg"),
            image_width: 1920,
            image_height: 1080,
            user: "mock_user".into(),
        })
        .collect();

    let resp = PixabayResponse { total: 1000, total_hits: 500, hits };
    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_search_images() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = PixabayRequest {
            q: "technology".into(),
            per_page: Some(15),
            page: None,
            image_type: Some("photo".into()),
        };
        let resp = search_images(&cache, &req);
        assert!(!resp.hits.is_empty());
        assert_eq!(resp.hits[0].kind, "photo");
        assert!(resp.total_hits > 0);
    }
}
