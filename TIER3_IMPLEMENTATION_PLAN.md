# Tier 3 Implementation Plan — Remaining 9 Services

**Date:** 2026-09-14  
**Status:** Implementation roadmap for T3.3 through T3.11  
**Foundation:** Patterns established in T3.1 (Research) and T3.2 (Script)

---

## Overview

This document provides detailed implementation instructions for completing the remaining 9 services in Tier 3. Each service follows the established patterns:

1. **HTTP Retry** — `@with_http_retry` for external APIs
2. **Response Validation** — Pydantic models for outputs
3. **Prosody Integration** — Inworld TTS markers where applicable
4. **Atomic Operations** — ON CONFLICT for database writes
5. **Cost Tracking** — Per-service usage logging
6. **Structured Logging** — Success + failure events

---

## T3.3 — Voice Service (CRITICAL PATH)

**Priority:** HIGHEST  
**Estimated Time:** 4-6 hours  
**Complexity:** 12 sub-items (master clock of pipeline)

### Current State

**File:** `backend/api/core/voice/main.py`

**Existing Features:**

- TTS provider integration (Inworld, ElevenLabs, etc.)
- Emotion mapping (local + LLM fallback)
- Per-sentence synthesis
- Audio quality scoring
- Voice style learning

**Missing Features:**

- Word-level alignment from Inworld
- Measured audio duration (ffprobe)
- Multi-take generation for hero moments
- Per-syllable emphasis timing
- Character-level reveal timing
- Per-phoneme SFX cues
- Voice-first music selection
- Hero-take pool cache

### Voice Service Implementation

#### 1. Add Word-Level Alignment

**Location:** After TTS synthesis in `synthesize()` function

```python
from media.word_alignment import get_word_timestamps, normalize_alignment

async def _get_word_alignment(audio_url: str, text: str, provider: str) -> list[dict]:
    """
    Extract word-level timestamps from synthesized audio.

    For Inworld: Use native word timestamps API
    For others: Use WhisperX fallback alignment
    """
    if provider == "inworld":
        # Inworld provides word timestamps in response
        # Extract from TTS response metadata
        word_timestamps = await _extract_inworld_timestamps(audio_url)
    else:
        # Fallback to WhisperX alignment
        word_timestamps = await get_word_timestamps(audio_url, text)

    # Normalize to standard format
    return normalize_alignment(word_timestamps)
```

**Add to synthesis loop:**

```python
# After TTS call
audio_result = await tts.synthesize(text=sentence["text"], voice_id=voice_id, ...)

# Get word alignment
word_alignment = await _get_word_alignment(
    audio_url=audio_result["audio_url"],
    text=sentence["text"],
    provider=tts.provider_name()
)

sentence["word_alignment"] = word_alignment
```

#### 2. Measure Real Duration with ffprobe

**Location:** After audio upload

```python
from media.ffprobe import get_audio_duration_ms

# After storage upload
audio_url = storage_result["url"]

# Measure real duration
duration_ms = await get_audio_duration_ms(audio_url)
sentence["duration_ms"] = duration_ms

logger.info(
    "voice.duration_measured",
    sentence_id=sentence.get("id"),
    duration_ms=duration_ms
)
```

#### 3. Multi-Take Generation for Hero Moments

**Location:** Before synthesis loop

```python
def _identify_hero_moments(segments: list[dict]) -> list[str]:
    """Identify sentences that need multi-take generation."""
    hero_sentences = []
    for seg in segments:
        if seg.get("is_hero_moment") or seg.get("section") == "hook":
            hero_sentences.append(seg.get("text"))
    return hero_sentences

async def _generate_multi_takes(
    text: str,
    voice_id: str,
    tts_provider,
    num_takes: int = 3
) -> list[dict]:
    """Generate multiple takes and select best one."""
    takes = []

    for take_num in range(num_takes):
        # Vary parameters slightly for each take
        params = _vary_tts_params(base_params, variation=0.1)

        result = await tts_provider.synthesize(
            text=text,
            voice_id=voice_id,
            **params
        )

        # Score take quality
        quality_score = await analyze_audio_quality(result["audio_url"])

        takes.append({
            "take_id": take_num + 1,
            "audio_url": result["audio_url"],
            "quality_score": quality_score,
            "params": params
        })

    # Select best take
    best_take = max(takes, key=lambda t: t["quality_score"])
    best_take["selected"] = True

    return takes
```

#### 4. Per-Syllable Emphasis Timing

**Requires:** `pyphen` library for syllabification

```python
import pyphen

def _get_syllable_timing(word: dict, emphasis: bool = False) -> list[dict]:
    """
    Break word into syllables with timing.

    Args:
        word: {"word": "breakthrough", "start_ms": 1000, "end_ms": 1500}
        emphasis: Whether this is an emphasis word

    Returns:
        [{"syllable": "break", "start_ms": 1000, "end_ms": 1200, "stress": True}, ...]
    """
    dic = pyphen.Pyphen(lang='en_US')
    syllables = dic.inserted(word["word"]).split('-')

    duration_ms = word["end_ms"] - word["start_ms"]
    syllable_duration = duration_ms / len(syllables)

    result = []
    current_time = word["start_ms"]

    for i, syl in enumerate(syllables):
        # Identify stress syllable (typically first or last for emphasis)
        is_stress = emphasis and (i == 0 or i == len(syllables) - 1)

        result.append({
            "syllable": syl,
            "start_ms": int(current_time),
            "end_ms": int(current_time + syllable_duration),
            "stress": is_stress
        })

        current_time += syllable_duration

    return result

# Add to word alignment processing
for word in word_alignment:
    if word["word"] in emphasis_words:
        word["syllables"] = _get_syllable_timing(word, emphasis=True)
        word["is_emphasis"] = True
```

#### 5. Character-Level Reveal Timing

```python
def _get_character_timing(word: dict) -> list[dict]:
    """
    Break word into characters with timing for reveal animations.

    Returns:
        [{"char": "b", "at_ms": 1000}, {"char": "r", "at_ms": 1050}, ...]
    """
    chars = list(word["word"])
    duration_ms = word["end_ms"] - word["start_ms"]
    char_duration = duration_ms / len(chars)

    result = []
    current_time = word["start_ms"]

    for char in chars:
        result.append({
            "char": char,
            "at_ms": int(current_time)
        })
        current_time += char_duration

    return result

# Add to word alignment
for word in word_alignment:
    word["chars"] = _get_character_timing(word)
```

#### 6. Per-Phoneme SFX Cues

**Requires:** `pronouncing` library (CMU dict)

```python
import pronouncing

def _get_phoneme_sfx_cues(word: dict) -> list[dict]:
    """
    Map phonemes to SFX cues for sound design.

    Example: "explosion" → [EH, K, S, P, L, OW, ZH, AH, N]
    Trigger SFX on plosives (P, B, T, D, K, G)
    """
    phones = pronouncing.phones_for_word(word["word"])
    if not phones:
        return []

    # Take first pronunciation
    phonemes = phones[0].split()

    # Map to SFX triggers
    plosives = {'P', 'B', 'T', 'D', 'K', 'G'}
    fricatives = {'F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH'}

    sfx_cues = []
    duration_ms = word["end_ms"] - word["start_ms"]
    phoneme_duration = duration_ms / len(phonemes)
    current_time = word["start_ms"]

    for phoneme in phonemes:
        # Strip stress markers (0, 1, 2)
        clean_phoneme = phoneme.rstrip('012')

        cue = {
            "phoneme": clean_phoneme,
            "at_ms": int(current_time),
            "sfx_type": None
        }

        if clean_phoneme in plosives:
            cue["sfx_type"] = "impact"
        elif clean_phoneme in fricatives:
            cue["sfx_type"] = "whoosh"

        if cue["sfx_type"]:
            sfx_cues.append(cue)

        current_time += phoneme_duration

    return sfx_cues

# Add to emphasis words
for word in word_alignment:
    if word.get("is_emphasis"):
        word["sfx_cues"] = _get_phoneme_sfx_cues(word)
```

#### 7. Extract Emphasis Hits

```python
def _extract_emphasis_hits(word_alignment: list[dict]) -> list[dict]:
    """
    Extract emphasis hit timings for downstream services (assets, music, direction).

    Returns:
        [{"word": "breakthrough", "at_ms": 1250, "intensity": 0.9}, ...]
    """
    emphasis_hits = []

    for word in word_alignment:
        if not word.get("is_emphasis"):
            continue

        # Find stress syllable timing
        syllables = word.get("syllables", [])
        stress_syllable = next((s for s in syllables if s.get("stress")), None)

        if stress_syllable:
            hit_time = stress_syllable["start_ms"]
        else:
            # Fallback to word midpoint
            hit_time = (word["start_ms"] + word["end_ms"]) // 2

        emphasis_hits.append({
            "word": word["word"],
            "at_ms": hit_time,
            "intensity": 0.9,  # Could be computed from audio amplitude
            "phoneme_density": len(word.get("sfx_cues", []))
        })

    return emphasis_hits
```

#### 8. Hero-Take Cache

```python
async def _cache_hero_take(
    text: str,
    channel_id: str,
    best_take: dict,
    cache_duration_days: int = 30
) -> None:
    """Cache hero take for reuse across videos."""
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO voice_hero_cache (
            channel_id, text_hash, audio_url, quality_score,
            tts_params, expires_at
        ) VALUES ($1, $2, $3, $4, $5, NOW() + INTERVAL '$6 days')
        ON CONFLICT (channel_id, text_hash)
        DO UPDATE SET
            audio_url = EXCLUDED.audio_url,
            quality_score = EXCLUDED.quality_score,
            updated_at = NOW()
        """,
        channel_id,
        hashlib.sha256(text.encode()).hexdigest(),
        best_take["audio_url"],
        best_take["quality_score"],
        json.dumps(best_take["params"]),
        cache_duration_days
    )

async def _get_cached_hero_take(text: str, channel_id: str) -> dict | None:
    """Retrieve cached hero take if available."""
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT audio_url, quality_score, tts_params
        FROM voice_hero_cache
        WHERE channel_id = $1
          AND text_hash = $2
          AND expires_at > NOW()
        """,
        channel_id,
        hashlib.sha256(text.encode()).hexdigest()
    )

    return dict(row) if row else None
```

#### 9. Output Schema Validation

```python
from pydantic import BaseModel, Field

class WordAlignment(BaseModel):
    word: str
    start_ms: int
    end_ms: int
    is_emphasis: bool = False
    syllables: list[dict] = Field(default_factory=list)
    chars: list[dict] = Field(default_factory=list)
    sfx_cues: list[dict] = Field(default_factory=list)

class VoiceSegment(BaseModel):
    segment_id: str
    audio_url: str
    duration_ms: int
    word_alignment: list[WordAlignment]
    emphasis_hits: list[dict] = Field(default_factory=list)
    multi_take_info: dict = Field(default_factory=dict)
    quality_score: float = 0.0

class VoiceOutput(BaseModel):
    segments: list[VoiceSegment]
    total_duration_ms: int
    emphasis_hits: list[dict]
    cost_usd: float
    provider: str

# Validate before returning
validated = VoiceOutput(
    segments=[VoiceSegment(**seg) for seg in voice_segments],
    total_duration_ms=sum(s["duration_ms"] for s in voice_segments),
    emphasis_hits=all_emphasis_hits,
    cost_usd=total_cost,
    provider=tts.provider_name()
)
```

### Database Migration

**File:** `infra/migrations/202608100001_tier3_voice_hero_cache.sql`

```sql
-- Migration: Tier 3 Voice Service - Hero Take Cache
-- Date: 2026-08-10
-- Purpose: Add hero take caching table

CREATE TABLE IF NOT EXISTS voice_hero_cache (
    id SERIAL PRIMARY KEY,
    channel_id TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    audio_url TEXT NOT NULL,
    quality_score FLOAT NOT NULL,
    tts_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE (channel_id, text_hash)
);

CREATE INDEX idx_voice_hero_cache_channel ON voice_hero_cache (channel_id);
CREATE INDEX idx_voice_hero_cache_expires ON voice_hero_cache (expires_at);

COMMENT ON TABLE voice_hero_cache IS 'Tier 3: Cache hero moment takes for reuse';
```

### Testing

**File:** `tests/test_tier3_voice.py`

```python
class TestVoiceService:
    @pytest.mark.asyncio
    async def test_word_alignment_present(self):
        """Voice output should include word-level alignment."""
        # Test implementation

    @pytest.mark.asyncio
    async def test_duration_measured_not_estimated(self):
        """Duration should be measured via ffprobe, not estimated."""
        # Test implementation

    @pytest.mark.asyncio
    async def test_hero_moments_multi_take(self):
        """Hero moments should generate multiple takes."""
        # Test implementation

    @pytest.mark.asyncio
    async def test_emphasis_hits_extracted(self):
        """Emphasis hits should be extracted for downstream services."""
        # Test implementation
```

---

## T3.4 — Assets Service

**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Dependencies:** Voice service (T3.3)

### Assets Service Implementation

#### 1. Add HTTP Retry for Asset APIs

```python
from core.http_retry import with_http_retry

@with_http_retry(max_attempts=3, base_delay=1.0)
async def _search_pexels(query: str, count: int = 5) -> list[dict]:
    """Search Pexels with retry logic."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": settings.pexels_api_key},
            params={"query": query, "per_page": count}
        )
        resp.raise_for_status()

        data = resp.json()
        if "videos" not in data:
            logger.warning("assets.pexels_invalid_response")
            return []

        return data["videos"]
```

#### 2. Voice-Aware Cut Suggestions

```python
def _generate_cut_suggestions(
    voice_manifest: dict,
    asset_duration_ms: int
) -> list[int]:
    """
    Generate cut suggestions aligned with voice emphasis hits.

    Args:
        voice_manifest: Output from voice service with emphasis_hits
        asset_duration_ms: Total duration of assets needed

    Returns:
        List of cut times in milliseconds
    """
    emphasis_hits = voice_manifest.get("emphasis_hits", [])

    # Start with emphasis hit timings
    cut_times = [hit["at_ms"] for hit in emphasis_hits]

    # Add cuts every 3-5 seconds if sparse
    if len(cut_times) < asset_duration_ms / 4000:
        current = 0
        while current < asset_duration_ms:
            if not any(abs(current - ct) < 1000 for ct in cut_times):
                cut_times.append(current)
            current += 3500  # 3.5 second intervals

    return sorted(cut_times)
```

#### 3. Validation

```python
class AssetOutput(BaseModel):
    assets: list[dict]
    cut_suggestions_ms: list[int]
    total_duration_ms: int
    coverage: float  # 0.0-1.0

# Validate
validated = AssetOutput(
    assets=selected_assets,
    cut_suggestions_ms=cut_times,
    total_duration_ms=sum(a["duration_ms"] for a in selected_assets),
    coverage=calculate_coverage(selected_assets, target_duration)
)
```

---

## T3.5 — Music Service

**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Dependencies:** Voice service (T3.3)

### Music Service Implementation

#### 1. Beat Detection

**Requires:** `librosa` library

```python
import librosa

async def _detect_beats(audio_url: str) -> dict:
    """
    Detect beats in music track using librosa.

    Returns:
        {
            "bpm": 128,
            "beat_map_ms": [0, 468, 937, 1406, ...],
            "confidence": 0.95
        }
    """
    # Download audio file
    audio_path = await _download_temp(audio_url)

    # Load audio
    y, sr = librosa.load(audio_path)

    # Detect tempo and beats
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

    # Convert frames to milliseconds
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beat_map_ms = [int(t * 1000) for t in beat_times]

    return {
        "bpm": int(tempo),
        "beat_map_ms": beat_map_ms,
        "confidence": 0.95  # Could compute from beat strength
    }
```

#### 2. Voice-Music Reconciliation

```python
def _reconcile_voice_beats(
    voice_emphasis_hits: list[dict],
    music_beat_map_ms: list[int],
    tolerance_ms: int = 100
) -> list[dict]:
    """
    Find hero moments where voice emphasis aligns with music beats.

    Returns:
        [
            {
                "at_ms": 550,
                "type": "voice_beat_sync",
                "voice_word": "breakthrough",
                "music_beat_ms": 468,
                "offset_ms": 82
            },
            ...
        ]
    """
    hero_moments = []

    for hit in voice_emphasis_hits:
        # Find nearest beat
        nearest_beat = min(
            music_beat_map_ms,
            key=lambda b: abs(b - hit["at_ms"])
        )

        offset = abs(nearest_beat - hit["at_ms"])

        if offset <= tolerance_ms:
            hero_moments.append({
                "at_ms": hit["at_ms"],
                "type": "voice_beat_sync",
                "voice_word": hit["word"],
                "music_beat_ms": nearest_beat,
                "offset_ms": offset,
                "intensity": hit["intensity"]
            })

    return hero_moments
```

---

## T3.6 — Thumbnail Service

**Priority:** LOW  
**Estimated Time:** 1 hour

### Thumbnail Service Implementation

#### 1. Vision QC Filter

```python
@with_http_retry(max_attempts=2, base_delay=1.0)
async def _predict_thumbnail_ctr(image_url: str) -> float:
    """
    Predict thumbnail CTR using vision model.

    Returns:
        Predicted CTR score (0.0-10.0)
    """
    vision_provider = ProviderRegistry.get("vision")

    result = await vision_provider.analyze(
        image_url=image_url,
        task="thumbnail_quality"
    )

    return result.get("ctr_score", 5.0)

# Filter low-quality thumbnails
candidates = await _generate_thumbnail_candidates(...)
scored = []

for candidate in candidates:
    ctr_score = await _predict_thumbnail_ctr(candidate["url"])
    candidate["ctr_score"] = ctr_score
    scored.append(candidate)

# Reject < 7.0
filtered = [c for c in scored if c["ctr_score"] >= 7.0]

if not filtered:
    logger.warning("thumbnail.all_rejected", count=len(candidates))
    # Fallback to template generation
```

---

## T3.7 — Direction Service (v3.1 Emitter)

**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Dependencies:** Voice service (T3.3)

### Direction Service Implementation

#### 1. Emit Timeline Anchors (≤500ms spacing)

```python
def _emit_timeline_keyframes(
    voice_manifest: dict,
    duration_ms: int,
    max_gap_ms: int = 500
) -> list[dict]:
    """
    Emit timeline keyframes at ≤500ms spacing.

    Returns:
        [
            {
                "at_ms": 0,
                "camera": {"position": {"x": 0, "y": 0, "z": 5}, "scale": 1.0},
                "ease": "easeInOutCubic"
            },
            ...
        ]
    """
    keyframes = []

    # Start keyframe
    keyframes.append({
        "at_ms": 0,
        "camera": {"position": {"x": 0, "y": 0, "z": 5}, "scale": 1.0, "rotation": 0},
        "ease": "easeInOutCubic"
    })

    # Add keyframes at emphasis hits
    for hit in voice_manifest.get("emphasis_hits", []):
        keyframes.append({
            "at_ms": hit["at_ms"],
            "camera": {
                "position": {"x": 0, "y": 0, "z": 4.5},
                "scale": 1.1,
                "rotation": 0
            },
            "ease": "easeOutQuad"
        })

    # Fill gaps > 500ms
    keyframes.sort(key=lambda k: k["at_ms"])
    filled = [keyframes[0]]

    for i in range(1, len(keyframes)):
        prev = filled[-1]
        curr = keyframes[i]
        gap = curr["at_ms"] - prev["at_ms"]

        if gap > max_gap_ms:
            # Insert interpolated keyframes
            num_fills = gap // max_gap_ms
            for j in range(1, num_fills + 1):
                filled.append({
                    "at_ms": prev["at_ms"] + (j * max_gap_ms),
                    "camera": _interpolate_camera(prev["camera"], curr["camera"], j / (num_fills + 1)),
                    "ease": "linear"
                })

        filled.append(curr)

    return filled
```

#### 2. Emit Word-Level Captions

```python
def _emit_captions(voice_manifest: dict) -> list[dict]:
    """
    Emit word-level captions from voice word alignment.

    Returns:
        [
            {
                "word": "breakthrough",
                "start_ms": 200,
                "end_ms": 650,
                "style": "emphasis",
                "chars": [{"ch": "b", "at_ms": 200}, ...]
            },
            ...
        ]
    """
    captions = []

    for segment in voice_manifest.get("segments", []):
        for word in segment.get("word_alignment", []):
            caption = {
                "word": word["word"],
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "style": "emphasis" if word.get("is_emphasis") else "normal",
                "chars": word.get("chars", [])
            }
            captions.append(caption)

    return captions
```

#### 3. Emit Micro-Beats

```python
def _emit_micro_beats(
    voice_emphasis_hits: list[dict],
    music_beat_map_ms: list[int]
) -> list[dict]:
    """
    Emit micro-beats (≤100ms precision) for visual effects.

    Returns:
        [
            {"at_ms": 550, "intensity": 0.9, "type": "zoom_punch"},
            {"at_ms": 2100, "intensity": 0.85, "type": "flash"},
            ...
        ]
    """
    micro_beats = []

    for hit in voice_emphasis_hits:
        # Determine effect type based on intensity
        if hit["intensity"] >= 0.9:
            effect_type = "zoom_punch"
        elif hit["intensity"] >= 0.7:
            effect_type = "flash"
        else:
            effect_type = "subtle_glow"

        micro_beats.append({
            "at_ms": hit["at_ms"],
            "intensity": hit["intensity"],
            "type": effect_type
        })

    return micro_beats
```

#### 4. Emit Audio Ducking Envelope

```python
def _emit_ducking_envelope(
    voice_segments: list[dict],
    total_duration_ms: int
) -> list[dict]:
    """
    Emit audio ducking envelope (music volume reduction during voice).

    Returns:
        [
            {"at_ms": 0, "music_volume_db": -12},
            {"at_ms": 200, "music_volume_db": -12},
            {"at_ms": 7850, "music_volume_db": 0},
            ...
        ]
    """
    envelope = []

    # Duck music during voice
    for segment in voice_segments:
        # Fade down before voice starts
        envelope.append({
            "at_ms": max(0, segment["start_ms"] - 200),
            "music_volume_db": 0
        })
        envelope.append({
            "at_ms": segment["start_ms"],
            "music_volume_db": -12
        })

        # Keep ducked during voice
        envelope.append({
            "at_ms": segment["end_ms"],
            "music_volume_db": -12
        })

        # Fade up after voice ends
        envelope.append({
            "at_ms": segment["end_ms"] + 200,
            "music_volume_db": 0
        })

    return envelope
```

#### 5. Validation

```python
class DirectionV3_1(BaseModel):
    version: str = "3.1"
    timeline: list[dict]
    captions: list[dict]
    micro_beats: list[dict]
    audio_track: dict
    layers: list[dict]
    validation: dict

def _validate_direction(direction: dict) -> dict:
    """Validate direction v3.1 output."""
    timeline = direction["timeline"]

    # Check max keyframe gap
    max_gap = 0
    for i in range(1, len(timeline)):
        gap = timeline[i]["at_ms"] - timeline[i-1]["at_ms"]
        max_gap = max(max_gap, gap)

    # Check caption coverage
    captions = direction["captions"]
    total_caption_duration = sum(
        c["end_ms"] - c["start_ms"] for c in captions
    )
    caption_coverage = total_caption_duration / direction["duration_ms"]

    return {
        "timeline_density_ok": max_gap <= 500,
        "max_keyframe_gap_ms": max_gap,
        "caption_coverage": caption_coverage,
        "micro_beat_count": len(direction["micro_beats"])
    }
```

---

## T3.8 — Assembly Service

**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Dependencies:** Direction service (T3.7)

### Assembly Service Implementation

#### 1. Validate v3.1 Timeline Density

```python
def _validate_timeline_density(direction: dict) -> tuple[bool, list[dict]]:
    """
    Validate timeline has keyframes every ≤500ms.

    Returns:
        (is_valid, gaps_to_fill)
    """
    timeline = direction["timeline"]
    gaps = []

    for i in range(1, len(timeline)):
        gap_ms = timeline[i]["at_ms"] - timeline[i-1]["at_ms"]
        if gap_ms > 500:
            gaps.append({
                "start_ms": timeline[i-1]["at_ms"],
                "end_ms": timeline[i]["at_ms"],
                "gap_ms": gap_ms
            })

    return len(gaps) == 0, gaps

# Auto-interpolate if sparse
is_valid, gaps = _validate_timeline_density(direction)

if not is_valid:
    logger.warning("assembly.timeline_sparse", gaps=len(gaps))
    direction["timeline"] = _interpolate_timeline(direction["timeline"], gaps)
```

#### 2. Timeout Controls

```python
async def _render_with_timeout(
    direction: dict,
    timeout_seconds: int = 300
) -> dict:
    """
    Render video with timeout control.

    Raises:
        TimeoutError if render exceeds timeout
    """
    try:
        result = await asyncio.wait_for(
            _render_video(direction),
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        logger.error("assembly.render_timeout", timeout=timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail=f"Render exceeded {timeout_seconds}s timeout"
        )
```

---

## T3.9 — Finishing Service

**Priority:** LOW  
**Estimated Time:** 1 hour

### Finishing Service Implementation

#### 1. DaVinci Resolve Availability Probe

```python
@with_http_retry(max_attempts=2, base_delay=0.5)
async def _check_resolve_available() -> bool:
    """Check if DaVinci Resolve is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:8080/health")
            return resp.status_code == 200
    except Exception:
        return False

# Use fallback if Resolve unavailable
resolve_available = await _check_resolve_available()

if resolve_available:
    result = await _apply_resolve_grade(video_url)
else:
    logger.warning("finishing.resolve_unavailable")
    result = await _apply_ffmpeg_fallback(video_url)
```

---

## T3.10 — Delivery Service

**Priority:** MEDIUM  
**Estimated Time:** 2 hours

### Delivery Service Implementation

#### 1. Scheduled Publish Support

```python
class DeliveryRequest(BaseModel):
    video_url: str
    metadata: dict
    scheduled_publish_time: datetime | None = None

async def _schedule_publish(
    video_id: str,
    scheduled_time: datetime
) -> None:
    """Schedule video publish for future time."""
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO scheduled_publishes (
            video_id, scheduled_time, status
        ) VALUES ($1, $2, 'pending')
        """,
        video_id,
        scheduled_time
    )

    logger.info(
        "delivery.publish_scheduled",
        video_id=video_id,
        scheduled_time=scheduled_time
    )
```

#### 2. YouTube Quota Tracking

```python
async def _track_youtube_quota(
    operation: str,
    quota_cost: int
) -> None:
    """Track YouTube API quota usage."""
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO youtube_quota_usage (
            operation, quota_cost, used_at
        ) VALUES ($1, $2, NOW())
        """,
        operation,
        quota_cost
    )

    # Check daily quota
    today_usage = await pool.fetchval(
        """
        SELECT SUM(quota_cost)
        FROM youtube_quota_usage
        WHERE used_at >= CURRENT_DATE
        """
    )

    if today_usage >= 10000:
        logger.error("delivery.quota_exceeded", usage=today_usage)
        raise HTTPException(
            status_code=429,
            detail="YouTube API quota exceeded for today"
        )
```

#### 3. Upload Retry

```python
@with_http_retry(max_attempts=3, base_delay=5.0)
async def _upload_to_youtube(
    video_path: str,
    metadata: dict
) -> dict:
    """Upload video to YouTube with retry logic."""
    youtube = ProviderRegistry.get("youtube")

    result = await youtube.upload(
        video_path=video_path,
        title=metadata["title"],
        description=metadata["description"],
        tags=metadata["tags"],
        privacy=metadata.get("privacy", "private")
    )

    # Track quota
    await _track_youtube_quota("video.insert", 1600)

    return result
```

---

## T3.11 — Brand + Editor Services

**Priority:** LOW  
**Estimated Time:** 2 hours (1 hour each)

### Brand Service

#### 1. Atomic Brand DNA Writes

```python
async def _update_brand_dna(
    channel_id: str,
    updates: dict
) -> None:
    """Atomically update brand DNA."""
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO brand_dna (
            channel_id, brand_voice, narrative_rhythm,
            emotional_contract, updated_at
        ) VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (channel_id)
        DO UPDATE SET
            brand_voice = EXCLUDED.brand_voice,
            narrative_rhythm = EXCLUDED.narrative_rhythm,
            emotional_contract = EXCLUDED.emotional_contract,
            updated_at = NOW()
        """,
        channel_id,
        updates.get("brand_voice"),
        updates.get("narrative_rhythm"),
        updates.get("emotional_contract")
    )
```

### Editor Service

#### 1. Frame-Accurate QC Gate

```python
async def _validate_rendered_frame(
    video_url: str,
    frame_number: int,
    expected_content: dict
) -> dict:
    """Validate specific frame matches expected content."""
    # Extract frame
    frame_path = await _extract_frame(video_url, frame_number)

    # Vision QC
    vision = ProviderRegistry.get("vision")
    analysis = await vision.analyze(
        image_path=frame_path,
        task="content_verification"
    )

    # Compare with expected
    matches = _compare_content(analysis, expected_content)

    return {
        "frame_number": frame_number,
        "matches": matches,
        "confidence": analysis.get("confidence", 0.0)
    }
```

---

## Summary Checklist

### Per-Service Checklist

For each service:

- [ ] Add `@with_http_retry` to external API calls
- [ ] Create Pydantic output schema
- [ ] Validate response before returning
- [ ] Add structured logging (success + failure)
- [ ] Verify atomic database writes
- [ ] Add cost tracking
- [ ] Write unit tests (retry, validation, edge cases)
- [ ] Update `PIPELINE_TRACKER.md`

### Critical Path

1. ✅ T3.1 Research (DONE)
2. ✅ T3.2 Script (DONE)
3. ⏳ T3.3 Voice (CRITICAL - blocks 4, 5, 7)
4. ⏳ T3.7 Direction (HIGH - blocks 8)
5. ⏳ T3.4 Assets + T3.5 Music (parallel)
6. ⏳ T3.8 Assembly
7. ⏳ T3.6, T3.9, T3.10, T3.11 (parallel)

### Estimated Completion

**Remaining:** ~20-25 hours  
**With Focus:** 3-4 days  
**Target Confidence:** 82% (+7%)

---

## Next Action

**Start with T3.3 Voice Service** — This is the master clock of the pipeline and blocks multiple downstream services. Once Voice is complete, Assets, Music, and Direction can be implemented in parallel.

---

**Created:** 2026-09-14  
**Status:** Ready for implementation  
**Foundation:** Patterns proven in T3.1 + T3.2
