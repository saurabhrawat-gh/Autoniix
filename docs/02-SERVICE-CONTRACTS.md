# Service Contracts & Payload Schemas

> API contracts for all 10 services, Temporal activity specs, and provider interface definitions.

---

## Common Envelope

Every request to every service includes a standard envelope:

```json
{
  "request_id": "req_a1b2c3d4",
  "content_id": "VID_BS001_20250425_001",
  "channel_id": "BS001",
  "idempotency_key": "sha256:abcdef1234567890",
  "budget_guard": {
    "max_cost_usd": 2.50,
    "accrued_cost_usd": 0.42
  }
}
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `request_id` | string | yes | Unique per-request, for tracing |
| `content_id` | string | yes | Video identifier |
| `channel_id` | string | yes | Channel identifier |
| `idempotency_key` | string | yes | SHA256 of deterministic inputs; prevents duplicate work |
| `budget_guard` | object | yes | Pre-flight cost check; service aborts if `accrued + estimated > max` |

### Common Response Envelope

```json
{
  "request_id": "req_a1b2c3d4",
  "status": "success",
  "cost": {
    "provider": "openai",
    "model": "gpt-4o",
    "tokens_in": 1200,
    "tokens_out": 800,
    "cost_usd": 0.011
  },
  "data": { }
}
```

### Common Error Response

```json
{
  "request_id": "req_a1b2c3d4",
  "status": "error",
  "error": {
    "code": "PROVIDER_RATE_LIMIT",
    "message": "OpenAI rate limit exceeded",
    "retryable": true,
    "retry_after_seconds": 30
  }
}
```

Error codes: `PROVIDER_RATE_LIMIT`, `PROVIDER_ERROR`, `BUDGET_EXCEEDED`, `VALIDATION_ERROR`, `QUALITY_GATE_FAILED`, `CIRCUIT_OPEN`, `TIMEOUT`, `INTERNAL_ERROR`.

---

## Service 1: Research Service

**Port:** 5001

### POST /research

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0 },
  "payload": {
    "content_mode": "long_form",
    "niche": "health",
    "sub_niche": "body_signals",
    "topic_candidates": ["Why your body shivers", "What causes hiccups"],
    "constraints": {
      "min_sources": 5,
      "require_scientific": true,
      "avoid_topics": ["cancer diagnosis", "self-harm"]
    },
    "channel_dna": {
      "tone": "curious_authoritative",
      "audience_age": "25-45",
      "complexity_level": "accessible_expert"
    }
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "google", "model": "gemini-2.5-flash", "tokens_in": 3200, "tokens_out": 2800, "cost_usd": 0.0045 },
  "data": {
    "selected_topic": "Why your body shivers",
    "research_package": {
      "core_facts": [
        { "claim": "Shivering generates heat through muscle contraction", "confidence": 0.95, "source": "https://pubmed.ncbi.nlm.nih.gov/...", "source_type": "peer_reviewed" }
      ],
      "competitor_analysis": {
        "top_videos": [ { "title": "...", "views": 1200000, "channel": "...", "gap": "No mention of fever shivering" } ],
        "content_gap": "Emotional shivering (frisson) not covered"
      },
      "angle": "The 4 types of shivers your body produces (and what each means)",
      "hook_seeds": ["Your body has a secret heating system", "That random shiver? It's not what you think"],
      "research_depth_score": 8.7
    }
  }
}
```

---

## Service 2: Script Service

**Port:** 5002

### POST /script

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.05 },
  "payload": {
    "content_mode": "long_form",
    "research_package": { },
    "channel_dna": {
      "tone": "curious_authoritative",
      "target_wpm": 150,
      "target_duration_s": 480,
      "target_word_count": 1100,
      "forbidden_words": ["cure", "guaranteed", "miracle"],
      "golden_paragraphs": ["Example paragraph showing brand voice..."],
      "structure_template": "hook_problem_explain_reveal_cta"
    },
    "prompt_overrides": {}
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "anthropic", "model": "claude-sonnet", "tokens_in": 4500, "tokens_out": 3200, "cost_usd": 0.0615 },
  "data": {
    "script_base": {
      "title": "4 Types of Shivers Your Body Produces (And What Each Means)",
      "scenes": [
        {
          "id": "s1",
          "role": "narration",
          "text_raw": "Right now, your muscles are doing something you can't feel...",
          "claims": [{ "text": "muscles contract 20 times per second", "confidence": 0.92 }],
          "visual_intents": ["microscopic muscle fiber contraction", "cold weather reaction"],
          "pace_hint": "slow_build",
          "duration_hint_s": 15
        }
      ],
      "word_count": 1087,
      "estimated_duration_s": 435
    },
    "hook_variants": [
      { "id": "h1", "text": "Your body has a secret heating system...", "style": "curiosity_gap", "score": 8.9 },
      { "id": "h2", "text": "That random shiver? Your brain just triggered...", "style": "reveal", "score": 8.5 }
    ],
    "metadata": {
      "description": "...",
      "tags": ["body shivers", "why do we shiver", "body signals"],
      "category": "Science & Technology"
    },
    "scores": {
      "structure": 8.5,
      "engagement": 8.8,
      "accuracy": 9.1,
      "brand_voice": 8.3,
      "overall": 8.6
    }
  }
}
```

---

## Service 3: Voice Service

**Port:** 5003

### POST /voice

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.15 },
  "payload": {
    "voice_config": {
      "provider": "fish_audio",
      "voice_id": "ref_abc123",
      "target_wpm": 150,
      "format": "mp3",
      "bitrate": 128,
      "normalize": true
    },
    "scenes": [
      { "id": "s1", "text": "Right now, your muscles are doing something you can't feel...", "emotion": "curious", "emphasis": ["muscles", "feel"], "visual_only": false },
      { "id": "s2", "text": "", "emotion": null, "emphasis": [], "visual_only": true }
    ]
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "fish_audio", "model": "tts-v1", "bytes_charged": 4200, "cost_usd": 0.000063 },
  "data": {
    "scenes": [
      { "id": "s1", "audio_url": "s3://yt-automation/audio/BS001/VID_.../scene_s1.mp3", "duration_s": 8.2, "word_count": 12 },
      { "id": "s2", "audio_url": null, "duration_s": 0, "word_count": 0 }
    ],
    "total_duration_s": 8.2,
    "total_bytes_charged": 4200,
    "cache_hit": false
  }
}
```

---

## Service 4: Assets Service

**Port:** 5004

### POST /assets

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.20 },
  "payload": {
    "scenes": [
      { "scene_id": "s1", "search_terms": ["muscle fiber contraction 4k", "cold weather reaction"], "min_resolution": "1280x720", "duration_s": 8, "style_preference": "cinematic" }
    ],
    "music_config": {
      "mood_curve": ["tense", "curious", "resolve"],
      "bpm_target": 92,
      "genre": "ambient_cinematic",
      "duration_s": 480
    },
    "sfx_config": {
      "triggers": [
        { "scene_id": "s1", "type": "whoosh", "at_s": 2.0 }
      ]
    }
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "pixabay", "cost_usd": 0 },
  "data": {
    "asset_manifest": [
      {
        "scene_id": "s1",
        "clips": [
          { "id": "clip_001", "url": "s3://yt-automation/assets/.../stock_001.mp4", "source": "pexels", "resolution": "1920x1080", "duration_s": 12, "relevance_score": 8.5, "license": "free" }
        ]
      }
    ],
    "music": {
      "url": "s3://yt-automation/assets/.../music.mp3",
      "source": "freesound",
      "bpm": 90,
      "duration_s": 485,
      "license": "CC0"
    },
    "sfx": [
      { "trigger_id": "s1_whoosh", "url": "s3://yt-automation/assets/.../sfx_whoosh.mp3" }
    ],
    "cache_hits": 2,
    "dedup_filtered": 1
  }
}
```

---

## Service 5: Thumbnail Service

**Port:** 5005

### POST /thumbnail

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.30 },
  "payload": {
    "title": "4 Types of Shivers Your Body Produces",
    "hook": "Your body has a secret heating system",
    "niche": "health",
    "brand_config": {
      "primary_color": "#FF3B30",
      "accent_color": "#FFD60A",
      "font": "Montserrat",
      "style": "bold_cinematic"
    },
    "competitor_patterns": ["face_reaction", "split_text", "before_after"],
    "num_variants": 3
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "openai", "model": "dall-e-3", "cost_usd": 0.08 },
  "data": {
    "variants": [
      {
        "id": "thumb_v1",
        "concept": "Human silhouette with visible muscle fibers glowing, cold breath visible",
        "background_url": "s3://yt-automation/thumbnails/.../concept_1.png",
        "final_url": "s3://yt-automation/thumbnails/.../final_1.png",
        "layout": "text_left_image_right",
        "scores": { "ctr_prediction": 8.7, "mobile_readability": "pass", "title_alignment": 8.9 }
      }
    ],
    "selected": "thumb_v1",
    "qc_report": { "vision_model": "gpt-4o", "assessment": "Strong contrast, readable at mobile size" }
  }
}
```

---

## Service 6: Assembly Service

**Port:** 5006

### POST /assembly

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.50 },
  "payload": {
    "script_base": { },
    "voice_result": { "scenes": [] },
    "asset_manifest": { },
    "thumbnail_result": { },
    "channel_dna": { },
    "template": "hybrid-kinetic",
    "brand_config": { }
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "cost": { "provider": "openai", "model": "gpt-4o", "tokens_in": 8500, "tokens_out": 6200, "cost_usd": 0.083 },
  "data": {
    "v3_json": {
      "version": "3.0",
      "meta": { "video_id": "...", "channel_id": "BS001", "title": "...", "duration_target_seconds": 480, "aspect": "16:9", "fps": 30, "resolution": { "width": 1920, "height": 1080 } },
      "template": "hybrid-kinetic",
      "theme": { },
      "grade_preset": "fx.grade.cinematic_teal_orange",
      "segments": []
    },
    "v3_url": "s3://yt-automation/scripts/.../script_remotion.json",
    "quality_report": {
      "gates_passed": 28,
      "gates_total": 30,
      "gates_failed": ["asset_diversity"],
      "final_composite_score": 8.4,
      "compliance": { "policy_risk": "low", "ai_disclosure_required": true, "niche_disclaimers": ["For educational purposes only"] }
    },
    "content_fingerprint": "sha256:abc123..."
  }
}
```

---

## Service 7: Render Service (Remotion)

**Port:** 4000 (separate repo: `yt-automation-remotion`)

See `docs/06-REMOTION-INTEGRATION.md` for full integration contract.

### POST /api/render

**Request:** Direction v3 JSON envelope (see Remotion repo Zod schema).

**Response:**
```json
{ "renderId": "render_abc123", "status": "rendering", "estimatedDuration": 180 }
```

### GET /api/render/:id

```json
{ "renderId": "render_abc123", "status": "done", "progress": 1.0, "outputUrl": "s3://...", "duration": 145, "fileSize": 52428800 }
```

### Callback (POST to callbackUrl)

```json
{ "renderId": "render_abc123", "status": "done", "outputUrl": "s3://...", "fileSize": 52428800, "duration": 145 }
```

---

## Service 8: Delivery Service

**Port:** 5007

### POST /deliver

**Request:**
```json
{
  "request_id": "...",
  "content_id": "...",
  "channel_id": "BS001",
  "idempotency_key": "...",
  "budget_guard": { "max_cost_usd": 2.50, "accrued_cost_usd": 0.70 },
  "payload": {
    "video_url": "s3://yt-automation/renders/.../video.mp4",
    "thumbnail_url": "s3://yt-automation/thumbnails/.../final_1.png",
    "metadata": {
      "title": "4 Types of Shivers Your Body Produces (And What Each Means)",
      "description": "...",
      "tags": ["body shivers", "why do we shiver"],
      "category": "Science & Technology",
      "language": "en",
      "privacy": "public",
      "scheduled_publish_at": null
    },
    "compliance": {
      "ai_disclosure": true,
      "ai_disclosure_text": "This video was created with AI assistance.",
      "niche_disclaimers": ["For educational purposes only. Consult a healthcare professional."],
      "made_for_kids": false
    }
  }
}
```

**Response:**
```json
{
  "request_id": "...",
  "status": "success",
  "data": {
    "youtube_video_id": "dQw4w9WgXcQ",
    "upload_status": "processing",
    "thumbnail_set": true,
    "metadata_set": true
  }
}
```

---

## Service 9: Analytics Service

**Port:** 5008

### POST /analytics

**Request:**
```json
{
  "request_id": "...",
  "channel_id": "BS001",
  "payload": {
    "lookback_days": 30,
    "metrics": ["views", "ctr", "retention", "watch_time", "subscriber_gain"]
  }
}
```

**Response:**
```json
{
  "data": {
    "channel_id": "BS001",
    "period": "2025-03-26 to 2025-04-25",
    "summary": { "total_views": 45000, "avg_ctr": 6.2, "avg_retention": 48.5, "subscriber_gain": 320 },
    "top_performers": [ { "video_id": "...", "views": 12000, "ctr": 8.1 } ],
    "patterns": [ { "insight": "Curiosity-gap hooks outperform reveal hooks by 40%", "confidence": 0.82 } ],
    "recommendations": [ "Increase use of data visualization scenes", "Test shorter intros (< 10s)" ]
  }
}
```

### POST /trends

```json
{
  "payload": {
    "niches": ["health", "finance", "psychology"],
    "sources": ["youtube_trending", "google_trends", "reddit"]
  }
}
```

---

## Service 10: Admin Service

**Port:** 5009

### REST API

| Method | Path | Purpose |
|--------|------|---------|
| GET | /channels | List all channels |
| POST | /channels | Create channel |
| PATCH | /channels/:id | Update channel config |
| DELETE | /channels/:id | Disable channel |
| GET | /videos | List videos (filterable) |
| GET | /videos/:id | Video detail + artifacts |
| POST | /system/pause | Pause all production |
| POST | /system/resume | Resume production |
| POST | /system/emergency-stop | Emergency stop |
| GET | /system/status | System health + budget |
| PATCH | /config/:key | Update system config |
| GET | /audit | Audit log (paginated) |
| GET | /costs | Cost report (by date/channel) |

All endpoints require `Authorization: Bearer <jwt>`. Roles: `admin` (full), `operator` (channels + system), `viewer` (read-only).

---

## Temporal Activity Contracts

### Retry Policies

| Activity | max_attempts | initial_interval | backoff | max_interval | non_retryable_errors |
|----------|-------------|------------------|---------|-------------|---------------------|
| research | 3 | 10s | 2.0 | 60s | BUDGET_EXCEEDED, VALIDATION_ERROR |
| script | 2 | 15s | 2.0 | 60s | BUDGET_EXCEEDED, VALIDATION_ERROR |
| voice | 3 | 5s | 2.0 | 30s | BUDGET_EXCEEDED |
| assets | 2 | 10s | 2.0 | 60s | BUDGET_EXCEEDED |
| thumbnail | 2 | 10s | 2.0 | 60s | BUDGET_EXCEEDED |
| assembly | 2 | 10s | 2.0 | 60s | BUDGET_EXCEEDED, QUALITY_GATE_FAILED |
| render | 2 | 30s | 2.0 | 120s | BUDGET_EXCEEDED |
| delivery | 3 | 10s | 2.0 | 60s | VALIDATION_ERROR |

### Timeouts (start_to_close)

| Activity | Timeout | Heartbeat |
|----------|---------|-----------|
| research | 5 min | — |
| script | 10 min | — |
| voice | 5 min | — |
| assets | 5 min | — |
| thumbnail | 5 min | — |
| assembly | 8 min | — |
| render | 20 min | 2 min |
| delivery | 5 min | — |

### Idempotency

Every activity receives an `idempotency_key` computed as:

```python
import hashlib
key = hashlib.sha256(
    f"{content_id}:{activity_name}:{stable_input_hash}".encode()
).hexdigest()
```

Services check Redis for this key before processing. If found, return cached result. This prevents duplicate work on retries.
