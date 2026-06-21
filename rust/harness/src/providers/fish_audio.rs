//! Fish Audio TTS mock — returns a valid silent WAV file.

use serde::{Deserialize, Serialize};

use super::ProviderCache;

#[derive(Debug, Serialize, Deserialize)]
pub struct FishAudioRequest {
    pub text: String,
    pub voice_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
}

/// Mock Fish Audio TTS — returns a valid silent WAV file.
pub fn synthesize(cache: &ProviderCache, req: &FishAudioRequest) -> Vec<u8> {
    let key = ProviderCache::key(
        "fish_audio",
        &serde_json::to_string(req).unwrap_or_default(),
    );

    if let Some(bytes) = cache.get_bytes(&key, "wav") {
        return bytes;
    }

    // Duration approximation: ~150 words/min, 44100 Hz, 16-bit mono
    let word_count = req.text.split_whitespace().count().max(1);
    let duration_secs = ((word_count as f32 / 150.0) * 60.0).ceil() as usize;
    let wav = silent_wav(duration_secs.max(1));

    cache.set_bytes(&key, "wav", &wav);
    wav
}

/// Generate a silent PCM WAV file (mono, 44100 Hz, 16-bit).
fn silent_wav(duration_secs: usize) -> Vec<u8> {
    const SAMPLE_RATE: u32 = 44_100;
    const CHANNELS: u16 = 1;
    const BITS: u16 = 16;

    let num_samples = duration_secs * SAMPLE_RATE as usize;
    let data_size = num_samples * (BITS / 8) as usize;
    let file_size = data_size + 36;

    let mut buf = Vec::with_capacity(file_size + 8);
    // RIFF header
    buf.extend_from_slice(b"RIFF");
    buf.extend_from_slice(&(file_size as u32).to_le_bytes());
    buf.extend_from_slice(b"WAVE");
    // fmt chunk
    buf.extend_from_slice(b"fmt ");
    buf.extend_from_slice(&16u32.to_le_bytes()); // chunk size
    buf.extend_from_slice(&1u16.to_le_bytes()); // PCM
    buf.extend_from_slice(&CHANNELS.to_le_bytes());
    buf.extend_from_slice(&SAMPLE_RATE.to_le_bytes());
    buf.extend_from_slice(&(SAMPLE_RATE * CHANNELS as u32 * BITS as u32 / 8).to_le_bytes());
    buf.extend_from_slice(&(CHANNELS * BITS / 8).to_le_bytes());
    buf.extend_from_slice(&BITS.to_le_bytes());
    // data chunk
    buf.extend_from_slice(b"data");
    buf.extend_from_slice(&(data_size as u32).to_le_bytes());
    buf.extend(std::iter::repeat(0u8).take(data_size));

    buf
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_synthesize_returns_wav() {
        let cache = ProviderCache::new(tempdir().unwrap().keep(), true);
        let req = FishAudioRequest {
            text: "Hello world this is a test".into(),
            voice_id: "test_voice".into(),
            speed: None,
            format: None,
        };
        let wav = synthesize(&cache, &req);
        assert!(wav.starts_with(b"RIFF"), "should start with RIFF header");
        assert!(&wav[8..12] == b"WAVE", "should contain WAVE identifier");
        assert!(wav.len() > 44, "should have audio data beyond header");
    }

    #[test]
    fn test_synthesize_cached() {
        let cache = ProviderCache::new(tempdir().unwrap().keep(), true);
        let req = FishAudioRequest {
            text: "Cache test sentence".into(),
            voice_id: "v1".into(),
            speed: None,
            format: None,
        };
        let w1 = synthesize(&cache, &req);
        let w2 = synthesize(&cache, &req);
        assert_eq!(w1, w2);
    }
}
