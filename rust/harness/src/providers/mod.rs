//! Provider mock harness — typed mocks for 8 external APIs.
//!
//! Saves ~$500/week in testing costs by returning cached mock responses
//! instead of calling real APIs. Cache is keyed by SHA-256 of the request.
//!
//! Providers:
//! 1. OpenAI   (GPT-4, GPT-4o, embeddings)
//! 2. Anthropic (Claude)
//! 3. Fish Audio (TTS → WAV bytes)
//! 4. DALL-E   (image generation)
//! 5. Pexels   (stock photos)
//! 6. Pixabay  (stock photos)
//! 7. SerpAPI  (web search)
//! 8. YouTube  (video metadata)
//! 9. Gemini   (Google AI)

pub mod anthropic;
pub mod dalle;
pub mod fish_audio;
pub mod gemini;
pub mod openai;
pub mod pexels;
pub mod pixabay;
pub mod serpapi;
pub mod youtube;

use std::path::PathBuf;

use sha2::{Digest, Sha256};

/// Shared cache layer for all provider mocks.
pub struct ProviderCache {
    pub dir: PathBuf,
    pub enabled: bool,
}

impl ProviderCache {
    pub fn new(dir: impl Into<PathBuf>, enabled: bool) -> Self {
        let dir = dir.into();
        std::fs::create_dir_all(&dir).ok();
        Self { dir, enabled }
    }

    /// Default: `tests/fixtures/providers/` relative to workspace root.
    pub fn default_for_tests() -> Self {
        let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap_or(&PathBuf::from("."))
            .parent()
            .unwrap_or(&PathBuf::from("."))
            .join("tests")
            .join("fixtures")
            .join("providers");
        Self::new(dir, true)
    }

    /// SHA-256 cache key from a request body string.
    pub fn key(provider: &str, request_repr: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!("{provider}:{request_repr}"));
        let hash = hasher.finalize();
        format!("{provider}_{:x}", &hash)[..provider.len() + 17].to_string()
    }

    pub fn get_json(&self, key: &str) -> Option<serde_json::Value> {
        if !self.enabled {
            return None;
        }
        let path = self.dir.join(format!("{key}.json"));
        std::fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
    }

    pub fn set_json(&self, key: &str, value: &serde_json::Value) {
        if !self.enabled {
            return;
        }
        let path = self.dir.join(format!("{key}.json"));
        if let Ok(s) = serde_json::to_string_pretty(value) {
            std::fs::write(path, s).ok();
        }
    }

    pub fn get_bytes(&self, key: &str, ext: &str) -> Option<Vec<u8>> {
        if !self.enabled {
            return None;
        }
        let path = self.dir.join(format!("{key}.{ext}"));
        std::fs::read(path).ok()
    }

    pub fn set_bytes(&self, key: &str, ext: &str, data: &[u8]) {
        if !self.enabled {
            return;
        }
        let path = self.dir.join(format!("{key}.{ext}"));
        std::fs::write(path, data).ok();
    }
}
