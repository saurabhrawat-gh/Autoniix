"""Audio Quality Scorer — Local audio analysis using librosa.

Analyzes TTS output audio for quality metrics:
- SNR (Signal-to-Noise Ratio)
- RMS energy consistency
- Zero-crossing rate (indicates noise/artifacts)
- Spectral centroid (brightness)
- Duration accuracy
- Naturalness heuristics

Intelligence cost: $0.00 — all computation is local via librosa.
"""
from __future__ import annotations

import asyncio
import io
import struct
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

# Lazy-load librosa (heavy import)
_librosa = None
_librosa_lock = asyncio.Lock()


async def _get_librosa():
    global _librosa
    if _librosa is not None:
        return _librosa
    async with _librosa_lock:
        if _librosa is not None:
            return _librosa

        def _load():
            import librosa
            return librosa

        _librosa = await asyncio.to_thread(_load)
        logger.info("audio_quality.librosa_loaded")
        return _librosa


def _quick_audio_stats(audio_bytes: bytes) -> dict:
    """Fast audio stats without librosa — for when speed matters over detail."""
    if not audio_bytes or len(audio_bytes) < 100:
        return {"valid": False, "error": "Audio too short"}

    size_kb = len(audio_bytes) / 1024
    # Rough duration estimate (MP3 at ~128kbps)
    estimated_duration_s = size_kb / 16.0

    return {
        "valid": True,
        "size_kb": round(size_kb, 1),
        "estimated_duration_s": round(estimated_duration_s, 2),
        "format_ok": audio_bytes[:3] in (b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'),
    }


async def analyze_audio_quality(audio_bytes: bytes, expected_duration_s: float = 0,
                                 expected_wpm: float = 150) -> dict:
    """Full audio quality analysis using librosa.
    
    Returns quality metrics and a composite score (1-10).
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return {"quality_score": 1.0, "error": "No audio data", "metrics": {}}

    try:
        librosa = await _get_librosa()

        def _analyze():
            import soundfile as sf

            # Load audio
            audio_buf = io.BytesIO(audio_bytes)
            try:
                y, sr = sf.read(audio_buf)
                if len(y.shape) > 1:
                    y = y.mean(axis=1)  # Convert stereo to mono
                y = y.astype(np.float32)
            except Exception:
                # Try librosa as fallback
                audio_buf.seek(0)
                y, sr = librosa.load(audio_buf, sr=None, mono=True)

            duration_s = len(y) / sr if sr > 0 else 0

            # RMS Energy
            rms = np.sqrt(np.mean(y ** 2))

            # Zero-crossing rate (high = noisy/artifacts)
            zcr = np.mean(np.abs(np.diff(np.signbit(y).astype(int))))

            # Spectral centroid (brightness)
            spec_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

            # SNR estimation (simple: signal power / noise floor estimate)
            frame_length = min(2048, len(y))
            if frame_length > 0:
                rms_frames = librosa.feature.rms(y=y, frame_length=frame_length)[0]
                noise_floor = np.percentile(rms_frames, 5)
                signal_peak = np.percentile(rms_frames, 95)
                if noise_floor > 0:
                    snr_db = 20 * np.log10(signal_peak / noise_floor)
                else:
                    snr_db = 40.0  # Very clean
            else:
                snr_db = 0.0

            # Silence detection
            silence_frames = np.sum(rms_frames < noise_floor * 1.5)
            silence_ratio = silence_frames / max(len(rms_frames), 1)

            return {
                "duration_s": round(duration_s, 3),
                "sample_rate": sr,
                "rms_energy": round(float(rms), 6),
                "zero_crossing_rate": round(float(zcr), 6),
                "spectral_centroid": round(spec_centroid, 2),
                "snr_db": round(float(snr_db), 2),
                "silence_ratio": round(float(silence_ratio), 3),
            }

        metrics = await asyncio.to_thread(_analyze)

    except Exception as e:
        logger.warning("audio_quality.analysis_failed", error=str(e))
        # Fallback to quick stats
        quick = _quick_audio_stats(audio_bytes)
        return {
            "quality_score": 5.0 if quick.get("valid") else 1.0,
            "error": str(e),
            "metrics": quick,
            "used_fallback": True,
        }

    # Compute composite quality score
    score = 10.0
    issues = []

    # SNR check
    snr = metrics.get("snr_db", 0)
    if snr < 10:
        score -= 3.0
        issues.append(f"Very low SNR: {snr:.1f} dB")
    elif snr < 15:
        score -= 1.5
        issues.append(f"Low SNR: {snr:.1f} dB")
    elif snr < 20:
        score -= 0.5

    # Zero-crossing rate (artifact detection)
    zcr = metrics.get("zero_crossing_rate", 0)
    if zcr > 0.15:
        score -= 1.0
        issues.append(f"High zero-crossing rate: {zcr:.4f} (possible artifacts)")

    # Duration accuracy
    if expected_duration_s > 0:
        actual = metrics.get("duration_s", 0)
        deviation = abs(actual - expected_duration_s) / expected_duration_s
        if deviation > 0.3:
            score -= 1.5
            issues.append(f"Duration deviation: {deviation:.0%}")
        elif deviation > 0.15:
            score -= 0.5

    # RMS energy check (too quiet or clipping)
    rms = metrics.get("rms_energy", 0)
    if rms < 0.001:
        score -= 2.0
        issues.append("Audio is nearly silent")
    elif rms > 0.5:
        score -= 1.0
        issues.append("Audio may be clipping")

    # Silence ratio check
    silence = metrics.get("silence_ratio", 0)
    if silence > 0.4:
        score -= 1.0
        issues.append(f"High silence ratio: {silence:.0%}")

    score = max(1.0, round(score, 1))

    # Naturalness heuristic (based on spectral centroid range)
    centroid = metrics.get("spectral_centroid", 0)
    naturalness = 7.0
    if 1000 < centroid < 4000:
        naturalness = 8.5  # Speech-like frequency range
    elif 500 < centroid < 6000:
        naturalness = 7.0
    else:
        naturalness = 5.0

    return {
        "quality_score": score,
        "naturalness_score": round(naturalness, 1),
        "metrics": metrics,
        "issues": issues,
    }


def score_emotion_variety(emotion_map: list[dict]) -> dict:
    """Score the emotional variety of the generated speech."""
    if not emotion_map:
        return {"variety_score": 0, "unique_emotions": 0}

    emotions = [e.get("emotion", "neutral") for e in emotion_map]
    unique = set(emotions)
    total = len(emotions)

    # Shannon entropy-based variety
    from collections import Counter
    counts = Counter(emotions)
    entropy = -sum((c / total) * np.log2(c / total) for c in counts.values() if c > 0)
    max_entropy = np.log2(len(unique)) if len(unique) > 1 else 1

    variety_score = (entropy / max_entropy * 10) if max_entropy > 0 else 0

    return {
        "variety_score": round(variety_score, 1),
        "unique_emotions": len(unique),
        "emotion_distribution": dict(counts),
        "entropy": round(entropy, 3),
    }
