//! YouTube Data API v3 mock — search, videos, channels.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum YouTubeEndpoint {
    Search,
    Videos,
    Channels,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct YouTubeSearchRequest {
    pub q: String,
    #[serde(rename = "maxResults")]
    pub max_results: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub part: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct YouTubeVideoRequest {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub part: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct YouTubeResponse {
    pub kind: String,
    pub items: Vec<serde_json::Value>,
    #[serde(rename = "pageInfo")]
    pub page_info: PageInfo,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PageInfo {
    #[serde(rename = "totalResults")]
    pub total_results: u64,
    #[serde(rename = "resultsPerPage")]
    pub results_per_page: u32,
}

/// Mock YouTube search.
pub fn search(cache: &ProviderCache, req: &YouTubeSearchRequest) -> YouTubeResponse {
    let key = ProviderCache::key("youtube_search", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let max = req.max_results.unwrap_or(5).min(3);
    let items = (0..max)
        .map(|i| {
            serde_json::json!({
                "kind": "youtube#searchResult",
                "id": {"kind": "youtube#video", "videoId": format!("mock_vid_{i}")},
                "snippet": {
                    "title": format!("Mock Video {}: {}", i + 1, req.q),
                    "description": format!("Mock description for {}", req.q),
                    "channelTitle": "Mock Channel",
                    "thumbnails": {
                        "default": {"url": format!("https://i.ytimg.com/vi/mock_{i}/default.jpg")},
                        "high": {"url": format!("https://i.ytimg.com/vi/mock_{i}/hqdefault.jpg")}
                    }
                }
            })
        })
        .collect();

    let resp = YouTubeResponse {
        kind: "youtube#searchListResponse".into(),
        items,
        page_info: PageInfo { total_results: 1000, results_per_page: max },
    };
    cache.set_json(&key, &serde_json::to_value(&resp).unwrap());
    resp
}

/// Mock YouTube video details.
pub fn video_details(cache: &ProviderCache, req: &YouTubeVideoRequest) -> YouTubeResponse {
    let key = ProviderCache::key("youtube_videos", &serde_json::to_string(req).unwrap_or_default());

    if let Some(cached) = cache.get_json(&key) {
        if let Ok(r) = serde_json::from_value(cached) {
            return r;
        }
    }

    let resp = YouTubeResponse {
        kind: "youtube#videoListResponse".into(),
        items: vec![serde_json::json!({
            "kind": "youtube#video",
            "id": req.id,
            "snippet": {
                "title": "Mock Video Title",
                "description": "Mock video description",
                "channelTitle": "Mock Channel"
            },
            "statistics": {
                "viewCount": "1000000",
                "likeCount": "50000",
                "commentCount": "1000"
            }
        })],
        page_info: PageInfo { total_results: 1, results_per_page: 1 },
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
        let req = YouTubeSearchRequest {
            q: "machine learning tutorial".into(),
            max_results: Some(5),
            part: None,
        };
        let resp = search(&cache, &req);
        assert_eq!(resp.kind, "youtube#searchListResponse");
        assert!(!resp.items.is_empty());
        assert_eq!(resp.items[0]["id"]["kind"], "youtube#video");
    }

    #[test]
    fn test_video_details() {
        let cache = ProviderCache::new(tempdir().unwrap().into_path(), true);
        let req = YouTubeVideoRequest { id: "test_video_abc".into(), part: None };
        let resp = video_details(&cache, &req);
        assert_eq!(resp.kind, "youtube#videoListResponse");
        assert_eq!(resp.items[0]["id"], "test_video_abc");
        assert!(resp.items[0]["statistics"]["viewCount"].is_string());
    }
}
